// edge_features.c — on-node feature extraction (skeleton). SDK: esp-dsp (managed component
// espressif/esp-dsp). Mirrors the server extractors so values are directly comparable; only
// the cheap OFFLOADABLE features. See design doc §7 and processing_layer .../extractors/.
#include "features/edge_features.h"
#include <string.h>
#include <math.h>
// #include "esp_dsp.h"

static int s_sr, s_nfft;

bool edge_features_init(int sample_rate, int n_fft) {
    s_sr = sample_rate; s_nfft = n_fft;
    // TODO: dsps_fft2r_init_fc32(NULL, n_fft); precompute Hann window + mel filterbank
    // (64 mels, fmax 8000) to match temporal/spectral_modulation server params.
    return true;
}

void edge_features_compute(const int16_t *x, int count, float noise_floor,
                           uint32_t mask, edge_features_t *out) {
    memset(out, 0, sizeof(*out));

    if (mask & EF_SNR) {
        // Cheapest: speech energy vs the VAD's tracked noise floor (same definition the VAD uses).
        double e = 0; for (int i = 0; i < count; i++) e += (double)x[i] * x[i];
        float rms = sqrtf((float)(e / (count > 0 ? count : 1)));
        out->snr = 20.0f * log10f((rms + 1e-6f) / (noise_floor + 1e-6f));
        out->has_snr = true;
    }
    if (mask & EF_SPECTRAL_FLATNESS) {
        // TODO: windowed FFT (dsps_fft2r_fc32) -> power spectrum -> geomean/aritmean.
        // out->spectral_flatness = expf(mean(log(P))) / mean(P);  out->has_spectral_flatness = true;
    }
    if (mask & EF_TEMPORAL_MODULATION) {
        // TODO: log-mel envelope -> 2-8 Hz band-pass (Butterworth) -> mean band energy.
    }
    if (mask & EF_SPECTRAL_MODULATION) {
        // TODO: FFT along the mel axis of the log-mel frames -> energy at ~2 cyc/oct bin.
    }
}
