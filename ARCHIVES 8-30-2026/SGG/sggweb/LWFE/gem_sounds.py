import math
import struct
import wave


def generate_wav(filename, samples, sample_rate=44100):
    """Writes raw float samples (-1.0 to 1.0) into a standard 16-bit PCM .wav file."""
    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(sample_rate)

        packed_data = bytearray()
        for s in samples:
            # Clamp sample between -1.0 and 1.0
            clamped = max(-1.0, min(1.0, s))
            # Convert to 16-bit signed integer (-32768 to 32767)
            integer_sample = int(clamped * 32767)
            packed_data.extend(struct.pack("<h", integer_sample))

        wav_file.writeframes(packed_data)


def create_dog_bark(filename="dog_bark.wav", duration=0.35, sample_rate=44100):
    """Synthesizes a punchy dog bark using pitch drop, noise, and envelope decay."""
    num_samples = int(sample_rate * duration)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples

        # Envelope: fast attack, quick decay
        envelope = math.exp(-12 * progress)

        # Pitch modulation: starts around 320 Hz and drops rapidly to 110 Hz
        freq = 320 * math.exp(-8 * progress) + 110
        phase = 2 * math.pi * freq * t

        # Fundamental tone + square/saw harmonics + slight noise for breath/chest rumble
        tone = math.sin(phase) + 0.5 * (1 if math.sin(phase) > 0 else -1)
        noise = (
            (hash(i) % 1000 / 1000.0) - 0.5
        ) * 0.3  # Deterministic pseudo-noise

        sample = (tone + noise) * envelope * 0.8
        samples.append(sample)

    generate_wav(filename, samples, sample_rate)
    print(f"Generated procedural audio file: {filename}")


def create_cat_meow(
    filename="cat_meow.wav", duration=0.85, sample_rate=44100
):
    """Synthesizes a feline meow using a pitch bend curve (rise and fall) and vocal harmonics."""
    num_samples = int(sample_rate * duration)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples

        # Smooth volume envelope (fade in, hold, fade out)
        if progress < 0.15:
            envelope = progress / 0.15
        elif progress > 0.7:
            envelope = (1.0 - progress) / 0.3
        else:
            envelope = 1.0

        # Meow Pitch Contour: Start ~450 Hz, rise to ~750 Hz, glide down to ~350 Hz
        if progress < 0.4:
            freq = 450 + (300 * (progress / 0.4))
        else:
            freq = 750 - (400 * ((progress - 0.4) / 0.6))

        phase = 2 * math.pi * freq * t

        # Nasal vocal timbre using multiple sine harmonics
        fundamental = math.sin(phase)
        second_harmonic = 0.6 * math.sin(2 * phase)
        third_harmonic = 0.3 * math.sin(3 * phase)

        sample = (
            (fundamental + second_harmonic + third_harmonic) * envelope * 0.5
        )
        samples.append(sample)

    generate_wav(filename, samples, sample_rate)
    print(f"Generated procedural audio file: {filename}")


if __name__ == "__main__":
    create_dog_bark()
    create_cat_meow()