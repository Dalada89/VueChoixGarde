"""Generate the project's CC0 toggle-on cue as a reproducible WAV file."""

import math
import struct
import wave
from pathlib import Path


def main() -> None:
    output = Path(__file__).parents[1] / "src/vuechoixgarde/resources/sounds/added.wav"
    sample_rate = 22_050
    sample_count = round(sample_rate * 0.10)
    frames = (
        struct.pack(
            "<h",
            round(
                4000
                * math.sin(2 * math.pi * (660 + 320 * index / sample_count) * index / sample_rate)
                * math.sin(math.pi * index / sample_count)
            ),
        )
        for index in range(sample_count)
    )
    with wave.open(str(output), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(sample_rate)
        sound.writeframes(b"".join(frames))


if __name__ == "__main__":
    main()
