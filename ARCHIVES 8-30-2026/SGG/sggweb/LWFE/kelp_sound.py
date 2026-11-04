import wave
import math
import struct

def generate_coin_sound(filename="coin.wav", duration=0.3, sample_rate=44100):
    # We want a fast rising pitch (like Mario)
    samples = []
    num_samples = int(duration * sample_rate)
    
    for i in range(num_samples):
        t = float(i) / sample_rate
        # Start at 988 Hz (B5), jump to 1319 Hz (E6)
        freq = 988.0 if t < 0.1 else 1319.0
        # Envelope to make it fade out smoothly
        envelope = math.exp(-15 * t) 
        
        # Generate a square wave for a chiptune feel
        value = math.sin(2.0 * math.pi * freq * t)
        square_wave = 1.0 if value > 0 else -1.0
        
        # Scale to 16-bit integer
        sample = int(square_wave * envelope * 32767)
        samples.append(sample)

    # Write to .wav file
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1) # Mono
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(sample_rate)
        for sample in samples:
            wav_file.writeframes(struct.pack('<h', sample))

generate_coin_sound("coin.wav")
print("Generated coin.wav!")