"""Edge-node capability protocol.

ESP32-S3 boards advertise what they can compute on-device; the server negotiates an
assignment (what each node should compute and send) and fills whatever the node can't do.
This module defines the schema + the negotiation policy. The data plane is carried by
AudioPayload.provided_features (the metrics a node already computed) and consumed by the
voice_metrics gap-filler, which skips the matching server extractors.

Three messages (over MQTT):
  1. advertise  node -> nodes/{id}/capabilities  (retained)  -> NodeCapabilities
  2. assign     server -> nodes/{id}/config                  -> NodeAssignment
  3. data       node -> voice/{user}/{board}/{env}           -> AudioPayload(+provided_features)
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# Pipeline metric names we currently TRUST an edge node to compute on-device. Conservative
# on purpose: only cheap, FFT/energy-based features an ESP32-S3 can produce at parity with
# the server. The clinically load-bearing markers (jitter/shimmer/HNR/formants/pyin-F0,
# speaker embeddings) stay server-side until on-device accuracy is validated. Grow this list
# as features are verified against the server extractors.
OFFLOADABLE_FEATURES: List[str] = [
    "spectral_flatness",
    "snr",
    "temporal_modulation",
    "spectral_modulation",
]

# Transport modes, cheapest/most-private first.
MODE_RAW = "raw"            # send raw audio (Tier 0, today's behavior)
MODE_SEGMENTS = "segments"  # send only VAD-gated speech (Tier 1)
MODE_FEATURES = "features"  # send precomputed features, no raw audio (Tier 2+)


@dataclass
class NodeProvides:
    vad: bool = False
    aec: bool = False
    doa: bool = False
    beamforming: bool = False
    speaker_gate: bool = False
    features: List[str] = field(default_factory=list)


@dataclass
class NodeCapabilities:
    """A node's self-reported capabilities (message 1)."""
    node_id: str
    firmware: str = "unknown"
    hardware: str = "esp32-s3"
    psram_mb: int = 0
    provides: NodeProvides = field(default_factory=NodeProvides)
    sample_rate: int = 16000
    frame_ms: int = 20
    max_payload_bytes: int = 8192

    @staticmethod
    def from_dict(d: dict) -> "NodeCapabilities":
        p = d.get("provides", {}) or {}
        return NodeCapabilities(
            node_id=str(d["node_id"]),
            firmware=str(d.get("firmware", "unknown")),
            hardware=str(d.get("hardware", "esp32-s3")),
            psram_mb=int(d.get("psram_mb", 0)),
            provides=NodeProvides(
                vad=bool(p.get("vad", False)),
                aec=bool(p.get("aec", False)),
                doa=bool(p.get("doa", False)),
                beamforming=bool(p.get("beamforming", False)),
                speaker_gate=bool(p.get("speaker_gate", False)),
                features=list(p.get("features", []) or []),
            ),
            sample_rate=int(d.get("sample_rate", 16000)),
            frame_ms=int(d.get("frame_ms", 20)),
            max_payload_bytes=int(d.get("max_payload_bytes", 8192)),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NodeAssignment:
    """What the server asks a node to compute and send (message 2)."""
    mode: str = MODE_RAW
    vad_gated: bool = False
    features: List[str] = field(default_factory=list)
    raw_on_uncertain: bool = True  # fall back to raw audio when node-VAD is unsure
    # Status-heartbeat cadence pushed to nodes. 1000ms was feature-report thinking; for
    # retained status heartbeats it meant 86k msgs/day/node (observed at first 4-node
    # fleet bring-up, 2026-07-09). 30s is plenty for the dashboard's online/stale view.
    report_interval_ms: int = 30000

    def to_dict(self) -> dict:
        return asdict(self)


def validate_capabilities(d: dict) -> List[str]:
    """Return a list of human-readable problems (empty == valid)."""
    problems = []
    if not isinstance(d, dict):
        return ["capabilities must be an object"]
    if not d.get("node_id"):
        problems.append("missing node_id")
    p = d.get("provides", {})
    if p and not isinstance(p, dict):
        problems.append("provides must be an object")
    for f in (p or {}).get("features", []) or []:
        if f not in OFFLOADABLE_FEATURES:
            problems.append(f"feature '{f}' is not in OFFLOADABLE_FEATURES (won't be trusted)")
    return problems


def negotiate_assignment(
    caps: NodeCapabilities,
    required_features: Optional[List[str]] = None,
) -> NodeAssignment:
    """Decide what a node should compute and send, from its capabilities.

    Policy (privacy-first): if the node can produce ALL the features the pipeline wants
    on-device, ask for feature-only transport (no raw audio leaves the node). Otherwise, if
    it can at least gate speech, ask for VAD-gated segments. Otherwise fall back to raw.
    Only features in OFFLOADABLE_FEATURES are ever trusted.
    """
    wanted = [f for f in (required_features or OFFLOADABLE_FEATURES) if f in OFFLOADABLE_FEATURES]
    node_features = [f for f in caps.provides.features if f in OFFLOADABLE_FEATURES]
    usable = [f for f in wanted if f in node_features]

    if usable and len(usable) == len(wanted):
        # Node covers everything the pipeline asked for -> features-only (most private).
        return NodeAssignment(mode=MODE_FEATURES, vad_gated=caps.provides.vad,
                              features=usable, raw_on_uncertain=caps.provides.vad)
    if caps.provides.vad:
        # Can't cover all features, but can gate speech -> send segments + whatever it can.
        return NodeAssignment(mode=MODE_SEGMENTS, vad_gated=True, features=usable)
    # Lowest-capability node -> raw audio, server does everything.
    return NodeAssignment(mode=MODE_RAW, vad_gated=False, features=[])
