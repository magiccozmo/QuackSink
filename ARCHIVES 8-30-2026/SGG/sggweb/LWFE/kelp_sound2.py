import wave
import math
import struct
import random

def generate_meow(filename="meow.wav", sample_rate=44100):
    duration = 0.6
    num_samples = int(duration * sample_rate)
    samples = []

    for i in range(num_samples):
        t = float(i) / sample_rate
        
        # Pitch contour: starts at 400Hz, dips to 300Hz, rises to 600Hz, then falls
        if t < 0.2:
            freq = 400 + (t / 0.2) * -100  # 400 -> 300
        elif t < 0.4:
            freq = 300 + ((t - 0.2) / 0.2) * 300 # 300 -> 600
        else:
            freq = 600 - ((t - 0.4) / 0.2) * 200 # 600 -> 400
            
        # The "meow" vowel sound needs harmonics, not just a pure sine wave
        # We'll mix the fundamental frequency with a few overtones
        value = math.sin(2.0 * math.pi * freq * t)
        value += 0.5 * math.sin(2.0 * math.pi * (freq * 2) * t)
        value += 0.25 * math.sin(2.0 * math.pi * (freq * 3) * t)
        
        # Volume envelope (fade in quickly, fade out slowly)
        if t < 0.05:
            envelope = t / 0.05
        else:
            envelope = max(0.0, 1.0 - ((t - 0.05) / (duration - 0.05)))
            
        sample = int((value / 1.75) * envelope * 32767)
        samples.append(sample)

    _write_wav(filename, samples, sample_rate)
    print(f"Generated {filename}!")

def generate_bark(filename="bark.wav", sample_rate=44100):
    duration = 0.25 # Barks are short
    num_samples = int(duration * sample_rate)
    samples = []

    for i in range(num_samples):
        t = float(i) / sample_rate
        
        # Pitch drops sharply (like a punch)
        freq = 250 * math.exp(-12 * t)
        
        # Generate a mix of the tone and white noise (breath/percussion)
        tone = math.sin(2.0 * math.pi * freq * t)
        noise = random.uniform(-1.0, 1.0)
        
        # A bark is mostly noise with a tonal thump at the beginning
        if t < 0.05:
            value = (tone * 0.7) + (noise * 0.3)
        else:
            value = (tone * 0.3) + (noise * 0.7)
            
        # Very sharp envelope (hits hard, dies fast)
        envelope = math.exp(-15 * t)
        
        sample = int(value * envelope * 32767)
        samples.append(sample)

    _write_wav(filename, samples, sample_rate)
    print(f"Generated {filename}!")

def _write_wav(filename, samples, sample_rate):
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for sample in samples:
            # Clamp to 16-bit limits to prevent overflow static
            sample = max(-32768, min(32767, sample))
            wav_file.writeframes(struct.pack('<h', sample))

# Generate both
generate_meow()
generate_bark()