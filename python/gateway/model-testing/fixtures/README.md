# Transcription fixture

`hello.wav` is synthetic speech generated with the macOS Samantha voice. It says:

> Hello. This is a gateway test.

The file contains no private recording. Its format is uncompressed WAV, 16,000 Hz, mono, signed 16-bit PCM; 34,871 frames give a duration of approximately 2.179 seconds.

If a transcription model is listed in the platform's Live catalog, its availability check uploads this fixture through the Respan Gateway. Any successful transcription response is accepted. Speech-generation checks use `Hello` as text input and do not use this WAV file.
