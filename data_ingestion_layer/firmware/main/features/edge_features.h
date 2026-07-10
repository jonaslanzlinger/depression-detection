// edge_features.h — on-node feature extraction (esp-dsp). Only the server's OFFLOADABLE
// features (cheap, FFT/energy-based). Heavy markers (jitter/shimmer/HNR/formants/pitch,
// embeddings) stay server-side. Validate these against the server extractors before trusting.
#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    bool  has_snr;                  float snr;                 // speech vs noise-floor energy (dB)
    bool  has_spectral_flatness;    float spectral_flatness;   // geomean/aritmean of power spectrum
    bool  has_temporal_modulation;  float temporal_modulation; // 2-8 Hz envelope band energy
    bool  has_spectral_modulation;  float spectral_modulation; // ~2 cyc/oct modulation energy
} edge_features_t;

// Init FFT tables / mel bank (call once). n_fft per the modulation extractors (1024).
bool edge_features_init(int sample_rate, int n_fft);

// Compute the enabled features over a speech chunk (int16 PCM). `enable_mask` selects which
// to compute (bitwise OR of EF_* below). `noise_floor` from the VAD feeds SNR cheaply.
#define EF_SNR                 (1u << 0)
#define EF_SPECTRAL_FLATNESS   (1u << 1)
#define EF_TEMPORAL_MODULATION (1u << 2)
#define EF_SPECTRAL_MODULATION (1u << 3)

void edge_features_compute(const int16_t *samples, int count, float noise_floor,
                           uint32_t enable_mask, edge_features_t *out);

#ifdef __cplusplus
}
#endif
