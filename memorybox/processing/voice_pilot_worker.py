"""Offline, one-model process. Input is local PCM WAV; no provider injection hook."""
import json
import socket
import sys
import wave

def no_network(*args, **kwargs):
    raise RuntimeError("pilot_network_disabled")

def main():
    socket.socket.connect = no_network
    socket.create_connection = no_network
    import torch
    torch.set_num_threads(1)
    from .titanet_adapter import load_model, encode
    model = load_model(sys.argv[1])
    print(json.dumps({"ready":True}), flush=True)
    for line in sys.stdin:
        request=json.loads(line)
        try:
            with wave.open(request['wav'],'rb') as f:
                if f.getnchannels()!=1 or f.getsampwidth()!=2 or f.getframerate()!=16000: raise ValueError('pcm_format')
                raw=f.readframes(f.getnframes())
            signal=torch.frombuffer(bytearray(raw),dtype=torch.int16).to(torch.float32)/32768.
            result=encode(model,signal)
            print(json.dumps({'vector':result},allow_nan=False),flush=True)
        except Exception as exc:
            print(json.dumps({'error_type':type(exc).__name__}),flush=True)
if __name__=='__main__': main()
