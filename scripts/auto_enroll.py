#!/usr/bin/env python3
"""
auto_enroll.py — Unsupervised primary-speaker voice profile bootstrap.

HOST MODE (default, run from repo root):
  1. Subscribe to voice/# on MQTT; collect for --collect-seconds (default 180).
  2. Per-segment SNR filter: use quality_metrics.snr if present, else compute
     from PCM (noise floor = 10th-percentile frame RMS; drop if SNR < --snr-floor).
  3. Save accepted WAV files to ae_staging/ inside the voice_profiling volume
     (processing_layer/user_profiling/voice_profiling/ae_staging/), which maps
     to /app/ae_staging/ inside the container.
  4. docker cp self → container /tmp/auto_enroll.py, then docker exec --embed-mode.
  5. Print cluster stats + before/after similarity distribution.

EMBED MODE (--embed-mode, always runs inside voice_profiling container):
  1. Load WAV files from /app/ae_staging/ (or --staging-dir).
  2. Compute d-vector per segment via Resemblyzer VoiceEncoder (same as recognition).
  3. Cluster online: assign to nearest centroid if cosine >= --cluster-threshold (0.75),
     else create new cluster.  Recompute centroid as running mean.
  4. Dominant cluster = largest; keep only if all members cosine >= 0.75 to its centroid.
  5. If dominant cluster >= --min-segments (15) AND covers > 50% of all collected segments:
       a. SAFETY: check if user already has a GOOD enrolled profile (norm > 0.5).
          If yes, enroll under <user_id>_auto and print promotion instructions.
       b. Concatenate cluster WAVs → single audio → POST to enrollment API.
  6. Print JSON result and cleanup staging dir.

Usage (host):
  python scripts/auto_enroll.py [options]

Options (host mode):
  --collect-seconds N     How long to listen on MQTT (default 180)
  --snr-floor DB          Minimum SNR in dB to keep a segment (default 8.0)
  --min-segments N        Minimum cluster size to enroll (default 15)
  --user-id ID            Target user id (default: bruno)
  --mqtt-host HOST        MQTT broker host (default: 127.0.0.1)
  --mqtt-port PORT        MQTT broker port (default: 1883)
  --container NAME        Docker container name for voice_profiling
  --progress-log FILE     Path to progress log (default: ~/ae-progress.log)
  --wav-dir DIR           Use local WAV files from DIR instead of MQTT collection

Options (embed mode, injected automatically):
  --embed-mode            Run embedding/clustering/enrollment (inside container)
  --staging-dir DIR       WAV staging directory (default: /app/ae_staging)
  --enroll-api URL        Enrollment API base URL (default: http://127.0.0.1:8000)
  --cluster-threshold F   Cosine similarity threshold for cluster membership (default 0.75)
"""

import argparse
import base64
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers (used in both modes)
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_PROFILING_DIR = REPO_ROOT / "processing_layer" / "user_profiling" / "voice_profiling"
DEFAULT_STAGING_SUBDIR = "ae_staging"
CONTAINER_STAGING = "/app/ae_staging"
CONTAINER_SCRIPT = "/tmp/auto_enroll.py"
CONTAINER_NAME = "audio-depression-detection-voice_profiling-1"
ENROLL_API = "http://127.0.0.1:8000"


def log(msg: str, progress_log: str = None):
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if progress_log:
        with open(progress_log, "a") as f:
            f.write(line + "\n")


def wav_bytes_to_float32(wav_bytes: bytes):
    """Decode WAV bytes → (float32 array, sample_rate). Returns (None,None) on error."""
    try:
        import soundfile as sf
        import numpy as np
        audio, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio, sr
    except Exception as e:
        return None, None


def compute_snr_db(audio: "np.ndarray", sr: int, frame_ms: int = 20) -> float:
    """
    Quick SNR estimate: signal RMS vs noise floor (10th percentile of frame RMS).
    Returns dB, or -inf if silent.
    """
    import numpy as np
    frame_len = int(sr * frame_ms / 1000)
    if frame_len < 1 or len(audio) < frame_len:
        return -math.inf
    n_frames = len(audio) // frame_len
    frames = audio[:n_frames * frame_len].reshape(n_frames, frame_len)
    frame_rms = np.sqrt((frames ** 2).mean(axis=1))
    signal_rms = float(np.sqrt((audio ** 2).mean()))
    noise_floor = float(np.percentile(frame_rms, 10))
    if noise_floor < 1e-9 or signal_rms < 1e-9:
        return -math.inf
    return 20.0 * math.log10(signal_rms / noise_floor)


# ─────────────────────────────────────────────────────────────────────────────
# HOST MODE: MQTT collection
# ─────────────────────────────────────────────────────────────────────────────

def load_env_creds(env_path: Path):
    """Load MQTT_USER and MQTT_PASS from .env file."""
    creds = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    return creds


def host_collect(args, staging_dir: Path, progress_log: str):
    """
    Subscribe to MQTT voice/# and collect WAV segments.
    Returns list of saved WAV file paths.
    """
    import numpy as np

    # Load MQTT credentials from .env
    env_path = REPO_ROOT / ".env"
    creds = load_env_creds(env_path)
    mqtt_user = creds.get("MQTT_USER", os.environ.get("MQTT_USER", ""))
    mqtt_pass = creds.get("MQTT_PASS", os.environ.get("MQTT_PASS", ""))

    try:
        import paho.mqtt.client as mqtt
        from paho.mqtt.client import CallbackAPIVersion
        client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    except Exception:
        import paho.mqtt.client as mqtt
        client = mqtt.Client()

    if mqtt_user:
        client.username_pw_set(mqtt_user, mqtt_pass)

    collected = []
    dropped_snr = [0]
    start_time = [None]

    staging_dir.mkdir(parents=True, exist_ok=True)

    def on_connect(c, userdata, flags, rc, *a):
        log(f"MQTT connected rc={rc}", progress_log)
        c.subscribe("voice/#")

    def on_message(c, userdata, msg):
        if start_time[0] is None:
            return  # not yet started

        elapsed = time.time() - start_time[0]
        if elapsed > args.collect_seconds:
            return

        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            return

        audio_b64 = payload.get("data") or ""
        if not audio_b64:
            return

        try:
            wav_bytes = base64.b64decode(audio_b64)
        except Exception:
            return

        if len(wav_bytes) < 100:
            return

        # SNR filter
        snr = None
        qm = payload.get("quality_metrics") or {}
        if qm.get("snr") is not None:
            snr = float(qm["snr"])
        else:
            audio, sr = wav_bytes_to_float32(wav_bytes)
            if audio is not None and sr is not None:
                snr = compute_snr_db(audio, sr)

        if snr is not None and snr < args.snr_floor:
            dropped_snr[0] += 1
            return

        # Save WAV to staging
        idx = len(collected)
        wav_path = staging_dir / f"seg_{idx:05d}.wav"
        wav_path.write_bytes(wav_bytes)
        collected.append(str(wav_path))

        if len(collected) % 5 == 0:
            log(f"  collected {len(collected)} segments, dropped_snr={dropped_snr[0]}, "
                f"elapsed={elapsed:.0f}s", progress_log)

    client.on_connect = on_connect
    client.on_message = on_message

    log(f"Connecting to MQTT {args.mqtt_host}:{args.mqtt_port} ...", progress_log)
    client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
    client.loop_start()

    log(f"Collection starting — {args.collect_seconds}s window, SNR floor={args.snr_floor} dB",
        progress_log)
    start_time[0] = time.time()

    while time.time() - start_time[0] < args.collect_seconds:
        time.sleep(1.0)

    client.loop_stop()
    client.disconnect()

    log(f"Collection complete: {len(collected)} segments kept, {dropped_snr[0]} dropped (SNR)",
        progress_log)
    return collected


def host_use_wav_dir(wav_dir: str, staging_dir: Path, args, progress_log: str):
    """Copy WAV files from an existing directory into staging (alternate to MQTT)."""
    import glob
    staging_dir.mkdir(parents=True, exist_ok=True)
    wavs = sorted(glob.glob(os.path.join(wav_dir, "*.wav")))
    log(f"WAV-dir mode: found {len(wavs)} WAVs in {wav_dir}", progress_log)
    copied = []
    for i, src in enumerate(wavs):
        dst = staging_dir / f"seg_{i:05d}.wav"
        shutil.copy2(src, dst)
        copied.append(str(dst))
    return copied


def host_run(args, progress_log: str):
    """Orchestrate collection + docker exec embed phase."""
    import numpy as np

    staging_dir = VOICE_PROFILING_DIR / DEFAULT_STAGING_SUBDIR

    # ── 1. Collection ──────────────────────────────────────────────────────
    if args.wav_dir:
        collected = host_use_wav_dir(args.wav_dir, staging_dir, args, progress_log)
    else:
        collected = host_collect(args, staging_dir, progress_log)

    if not collected:
        log("ERROR: No segments collected. Aborting.", progress_log)
        sys.exit(1)

    log(f"Staging dir: {staging_dir} ({len(collected)} WAVs)", progress_log)

    # ── 2. Copy this script into the container ────────────────────────────
    script_path = Path(__file__).resolve()
    container = args.container

    log(f"docker cp {script_path} → {container}:{CONTAINER_SCRIPT}", progress_log)
    cp_result = subprocess.run(
        ["docker", "cp", str(script_path), f"{container}:{CONTAINER_SCRIPT}"],
        capture_output=True, text=True
    )
    if cp_result.returncode != 0:
        log(f"ERROR: docker cp failed: {cp_result.stderr}", progress_log)
        sys.exit(1)

    # ── 3. Run embed mode inside container ────────────────────────────────
    embed_cmd = [
        "docker", "exec", container,
        "python", CONTAINER_SCRIPT,
        "--embed-mode",
        "--staging-dir", CONTAINER_STAGING,
        "--enroll-api", args.enroll_api,
        "--user-id", args.user_id,
        "--min-segments", str(args.min_segments),
        "--cluster-threshold", str(args.cluster_threshold),
        "--snr-floor", str(args.snr_floor),
    ]

    log(f"Running embed mode inside container: {' '.join(embed_cmd[3:])}", progress_log)
    result = subprocess.run(embed_cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        log(f"ERROR: embed mode exited {result.returncode}", progress_log)
        log(f"STDERR: {result.stderr[:1000]}", progress_log)
        log(f"STDOUT: {result.stdout[:1000]}", progress_log)
        sys.exit(1)

    # ── 4. Parse and display result ───────────────────────────────────────
    output = result.stdout
    log("─── Embed mode output ───", progress_log)
    for line in output.splitlines():
        log(f"  {line}", progress_log)

    # Try to parse the final JSON result line
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                result_json = json.loads(line)
                log("─── RESULT ───", progress_log)
                log(json.dumps(result_json, indent=2), progress_log)
            except Exception:
                pass
            break


# ─────────────────────────────────────────────────────────────────────────────
# EMBED MODE: runs inside voice_profiling container
# ─────────────────────────────────────────────────────────────────────────────

def cosine_sim(a, b):
    """Cosine similarity with zero-norm guard."""
    import numpy as np
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 1e-8 else 0.0


def cluster_embeddings(embeddings, threshold=0.75):
    """
    Online cosine-to-centroid clustering.
    Returns list of clusters, each a list of (index, embedding).
    """
    import numpy as np
    clusters = []   # list of {"centroid": np.ndarray, "members": [(idx, emb)]}

    for idx, emb in enumerate(embeddings):
        best_cluster = None
        best_sim = -1.0
        for c in clusters:
            sim = cosine_sim(emb, c["centroid"])
            if sim > best_sim:
                best_sim = sim
                best_cluster = c

        if best_cluster is not None and best_sim >= threshold:
            best_cluster["members"].append((idx, emb))
            # Update centroid as mean of all member embeddings
            member_embs = np.stack([e for _, e in best_cluster["members"]])
            best_cluster["centroid"] = member_embs.mean(axis=0)
        else:
            # New cluster
            clusters.append({
                "centroid": emb.copy(),
                "members": [(idx, emb)]
            })

    return clusters


def embed_mode_run(args):
    """Main logic for embed mode (inside container)."""
    import numpy as np
    import soundfile as sf
    import requests
    from resemblyzer import VoiceEncoder, preprocess_wav

    staging_dir = Path(args.staging_dir)
    enroll_api = args.enroll_api.rstrip("/")
    user_id = args.user_id
    min_segments = args.min_segments
    threshold = args.cluster_threshold

    print(f"[embed] staging_dir={staging_dir}, user_id={user_id}, "
          f"min_segments={min_segments}, cluster_threshold={threshold}")

    # ── 1. Load WAV files ──────────────────────────────────────────────────
    wav_files = sorted(staging_dir.glob("seg_*.wav"))
    print(f"[embed] Found {len(wav_files)} WAV files in staging dir")

    if not wav_files:
        print(json.dumps({"status": "error", "reason": "no WAV files in staging dir"}))
        return

    # ── 2. Compute embeddings ──────────────────────────────────────────────
    print("[embed] Loading VoiceEncoder (resemblyzer)...")
    encoder = VoiceEncoder()
    print("[embed] VoiceEncoder ready.")

    embeddings = []  # (wav_path, np.ndarray)
    failed = 0

    for wav_path in wav_files:
        try:
            wav_bytes = wav_path.read_bytes()
            audio, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            # preprocess: normalize + VAD trim (matches enrollment)
            processed = preprocess_wav(audio, source_sr=sr)
            if len(processed) < 1600:  # < 0.1s at 16kHz — skip
                failed += 1
                continue
            emb = encoder.embed_utterance(processed)
            embeddings.append((wav_path, emb))
        except Exception as e:
            print(f"[embed] WARN: failed to embed {wav_path.name}: {e}")
            failed += 1

    n_total = len(embeddings) + failed
    n_embedded = len(embeddings)
    print(f"[embed] Embedded {n_embedded}/{n_total} segments ({failed} failed/too-short)")

    if n_embedded < min_segments:
        result = {
            "status": "insufficient",
            "reason": f"only {n_embedded} embeddable segments, need {min_segments}",
            "n_total": n_total,
            "n_embedded": n_embedded,
        }
        print(json.dumps(result))
        _cleanup(staging_dir)
        return

    # ── 3. Cluster ────────────────────────────────────────────────────────
    emb_arrays = [e for _, e in embeddings]
    clusters = cluster_embeddings(emb_arrays, threshold=threshold)

    cluster_sizes = sorted([len(c["members"]) for c in clusters], reverse=True)
    dominant = max(clusters, key=lambda c: len(c["members"]))
    dom_size = len(dominant["members"])
    dom_frac = dom_size / n_embedded

    # Intra-cluster cosine stats for dominant cluster
    dom_centroid = dominant["centroid"]
    dom_sims = [cosine_sim(e, dom_centroid) for _, e in dominant["members"]]
    mean_intra = float(np.mean(dom_sims))
    min_intra = float(np.min(dom_sims))

    print(f"[embed] Clusters: {len(clusters)} total, sizes={cluster_sizes[:5]}...")
    print(f"[embed] Dominant cluster: n={dom_size}/{n_embedded} ({dom_frac:.1%}), "
          f"mean_intra_cos={mean_intra:.3f}, min_intra_cos={min_intra:.3f}")

    # ── 4. Check enrollment criteria ──────────────────────────────────────
    if dom_size < min_segments:
        result = {
            "status": "insufficient",
            "reason": f"dominant cluster has {dom_size} segments, need {min_segments}",
            "n_total": n_total, "n_embedded": n_embedded,
            "n_clusters": len(clusters),
            "dominant_cluster_size": dom_size,
            "dominant_cluster_fraction": round(dom_frac, 3),
            "mean_intra_cluster_cosine": round(mean_intra, 4),
        }
        print(json.dumps(result))
        _cleanup(staging_dir)
        return

    if dom_frac <= 0.50:
        result = {
            "status": "ambiguous",
            "reason": f"dominant cluster covers only {dom_frac:.1%} (<= 50%) of segments; "
                      "multiple speakers or noisy data?",
            "n_total": n_total, "n_embedded": n_embedded,
            "n_clusters": len(clusters),
            "dominant_cluster_size": dom_size,
            "dominant_cluster_fraction": round(dom_frac, 3),
            "mean_intra_cluster_cosine": round(mean_intra, 4),
        }
        print(json.dumps(result))
        _cleanup(staging_dir)
        return

    # ── 5. SAFETY: check existing enrollment ─────────────────────────────
    target_user = user_id
    promote_instructions = None

    try:
        resp = requests.get(f"{enroll_api}/management/users", timeout=10)
        if resp.ok:
            users = resp.json().get("users", [])
            for u in users:
                if u.get("user_id") == user_id:
                    existing_emb = u.get("voice_embedding", [])
                    if existing_emb:
                        norm = float(np.linalg.norm(np.array(existing_emb, dtype=np.float32)))
                        if norm > 0.5:
                            # Existing GOOD manual profile → use provisional id
                            target_user = f"{user_id}_auto"
                            promote_instructions = (
                                f"A good manual profile for '{user_id}' (embedding norm={norm:.3f}) "
                                f"already exists.  Auto-enrollment stored under '{target_user}'. "
                                f"To promote: re-enroll '{user_id}' via dashboard or:\n"
                                f"  curl -X POST {enroll_api}/enrollment/enroll \\\n"
                                f"    -F user_id={user_id} -F name=Bruno -F role=patient \\\n"
                                f"    -F audio_file=@<concat_of_cluster_wavs.wav>"
                            )
                            print(f"[embed] SAFETY: '{user_id}' has good profile (norm={norm:.3f}); "
                                  f"enrolling as '{target_user}'")
    except Exception as e:
        print(f"[embed] WARN: could not check existing enrollment: {e}")

    # ── 6. Build concatenated WAV from dominant cluster ───────────────────
    print(f"[embed] Concatenating {dom_size} cluster WAVs for enrollment...")
    cluster_indices = [idx for idx, _ in dominant["members"]]
    cluster_wav_paths = [embeddings[i][0] for i in cluster_indices]

    # Concatenate audio arrays (resample to 16 kHz for consistency)
    concat_audio = []
    target_sr = 16000
    for wp in cluster_wav_paths:
        try:
            audio, sr = sf.read(io.BytesIO(wp.read_bytes()), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr != target_sr:
                from scipy.signal import resample_poly
                g = math.gcd(sr, target_sr)
                audio = resample_poly(audio, target_sr // g, sr // g).astype(np.float32)
            # Small silence gap between segments
            concat_audio.append(audio)
            concat_audio.append(np.zeros(int(target_sr * 0.1), dtype=np.float32))
        except Exception as e:
            print(f"[embed] WARN: concat skip {wp.name}: {e}")

    if not concat_audio:
        print(json.dumps({"status": "error", "reason": "concat produced no audio"}))
        _cleanup(staging_dir)
        return

    concat_np = np.concatenate(concat_audio).astype(np.float32)
    duration_s = len(concat_np) / target_sr
    print(f"[embed] Concatenated audio: {duration_s:.1f}s @ {target_sr}Hz")

    # Write concatenated WAV to a temp file
    tmp_wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        sf.write(str(tmp_wav), concat_np, target_sr, subtype="PCM_16")
    except Exception as e:
        print(json.dumps({"status": "error", "reason": f"WAV write failed: {e}"}))
        _cleanup(staging_dir)
        return

    # ── 7. Enroll via API ─────────────────────────────────────────────────
    display_name = target_user.replace("_auto", " (auto)").title()
    print(f"[embed] POSTing to {enroll_api}/enrollment/enroll as user_id='{target_user}'...")

    try:
        with open(str(tmp_wav), "rb") as f:
            resp = requests.post(
                f"{enroll_api}/enrollment/enroll",
                data={"user_id": target_user, "name": display_name,
                      "role": "patient", "source": "auto"},
                files={"audio_file": ("enroll.wav", f, "audio/wav")},
                timeout=60,
            )
        if resp.status_code == 200:
            enroll_result = resp.json()
            enrolled = True
            print(f"[embed] Enrollment SUCCESS: {enroll_result}")
        else:
            enrolled = False
            enroll_result = {"http_status": resp.status_code, "body": resp.text[:300]}
            print(f"[embed] Enrollment FAILED: {enroll_result}")
    except Exception as e:
        enrolled = False
        enroll_result = {"error": str(e)}
        print(f"[embed] Enrollment ERROR: {e}")
    finally:
        tmp_wav.unlink(missing_ok=True)

    # ── 8. Build result JSON ──────────────────────────────────────────────
    result = {
        "status": "enrolled" if enrolled else "enrollment_failed",
        "enrolled_user_id": target_user if enrolled else None,
        "original_user_id": user_id,
        "provisional": target_user != user_id,
        "promote_instructions": promote_instructions,
        "n_total_segments_collected": n_total,
        "n_embeddable_segments": n_embedded,
        "n_clusters": len(clusters),
        "cluster_size_histogram": cluster_sizes[:10],
        "dominant_cluster_size": dom_size,
        "dominant_cluster_fraction": round(dom_frac, 3),
        "mean_intra_cluster_cosine": round(mean_intra, 4),
        "min_intra_cluster_cosine": round(min_intra, 4),
        "enrollment_api_response": enroll_result,
        "concat_audio_duration_s": round(duration_s, 1),
    }
    print(json.dumps(result))

    _cleanup(staging_dir)


def _cleanup(staging_dir: Path):
    """Remove all seg_*.wav files from staging dir."""
    removed = 0
    for f in staging_dir.glob("seg_*.wav"):
        try:
            f.unlink()
            removed += 1
        except Exception:
            pass
    print(f"[embed] Cleanup: removed {removed} staging WAV files from {staging_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)

    # Mode selector
    p.add_argument("--embed-mode", action="store_true",
                   help="Run embedding/clustering/enrollment (inside container)")

    # Shared
    p.add_argument("--user-id", default="bruno",
                   help="Target user id (default: bruno)")
    p.add_argument("--min-segments", type=int, default=15,
                   help="Minimum cluster size to enroll (default: 15)")
    p.add_argument("--cluster-threshold", type=float, default=0.75,
                   help="Cosine similarity threshold for cluster membership (default: 0.75)")
    p.add_argument("--snr-floor", type=float, default=8.0,
                   help="Minimum SNR in dB to keep a segment (default: 8.0)")

    # Host mode
    p.add_argument("--collect-seconds", type=int, default=180,
                   help="How long to listen on MQTT (default: 180)")
    p.add_argument("--mqtt-host", default="127.0.0.1",
                   help="MQTT broker host (default: 127.0.0.1)")
    p.add_argument("--mqtt-port", type=int, default=1883,
                   help="MQTT broker port (default: 1883)")
    p.add_argument("--container", default=CONTAINER_NAME,
                   help=f"Docker container name (default: {CONTAINER_NAME})")
    p.add_argument("--progress-log", default=os.path.expanduser("~/ae-progress.log"),
                   help="Path to progress log (default: ~/ae-progress.log)")
    p.add_argument("--wav-dir", default=None,
                   help="Use local WAV files from DIR instead of MQTT")
    p.add_argument("--enroll-api", default=ENROLL_API,
                   help=f"Enrollment API base URL (default: {ENROLL_API})")

    # Embed mode
    p.add_argument("--staging-dir", default=CONTAINER_STAGING,
                   help=f"WAV staging directory (default: {CONTAINER_STAGING})")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.embed_mode:
        embed_mode_run(args)
    else:
        progress_log = args.progress_log
        log("=== auto_enroll.py START ===", progress_log)
        log(f"user_id={args.user_id}, collect_seconds={args.collect_seconds}, "
            f"min_segments={args.min_segments}, snr_floor={args.snr_floor}",
            progress_log)
        host_run(args, progress_log)
        log("=== auto_enroll.py END ===", progress_log)
