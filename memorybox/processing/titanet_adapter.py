"""Local NVIDIA TitaNet-Large adapter; no pretrained download or legacy MB calls."""
from contextlib import redirect_stdout
import sys

def load_model(path):
    import hashlib
    from pathlib import Path
    from .voice_pilot import TITANET_SHA256
    with Path(path).open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=TITANET_SHA256:
            raise ValueError('unapproved_titanet_checkpoint')
    # NeMo logs must not corrupt the JSON protocol on stdout.
    with redirect_stdout(sys.stderr):
        import torch
        from nemo.collections.asr.models import EncDecSpeakerLabelModel
        torch.set_num_threads(1)
        model=EncDecSpeakerLabelModel.restore_from(restore_path=str(path),map_location=torch.device('cpu'))
        model.eval()
        cfg=model.cfg
        if int(cfg.preprocessor.sample_rate)!=16000 or int(cfg.decoder.emb_sizes)!=192:
            raise ValueError('titanet_checkpoint_contract_mismatch')
    return model

def encode(model, signal):
    import torch
    with redirect_stdout(sys.stderr), torch.inference_mode():
        _, embeddings=model.forward(input_signal=signal.unsqueeze(0),
                                    input_signal_length=torch.tensor([signal.numel()],dtype=torch.long))
        return embeddings.detach().cpu().flatten().tolist()
