import unittest
from unittest.mock import MagicMock, patch, mock_open
from memorybox.processing.titanet_adapter import load_model, encode
from memorybox.processing.voice_pilot import validate
from test_i13_voice_pilot import fixture

class TitaNetTests(unittest.TestCase):
    def test_only_new_checkpoint_contract_admitted(self):
        p=fixture();validate(p)
        p['thresholds']={'match':.55,'uncertain':.4}
        with self.assertRaises(ValueError):validate(p)
        p=fixture();p['model']['format']='torchscript_ecapa_192'
        with self.assertRaises(ValueError):validate(p)
    def test_restore_local_checkpoint_not_download(self):
        torch=MagicMock();api=MagicMock();model=api.EncDecSpeakerLabelModel.restore_from.return_value
        model.cfg.preprocessor.sample_rate=16000;model.cfg.decoder.emb_sizes=192
        with patch('pathlib.Path.open',mock_open(read_data=b'public model')),patch('hashlib.file_digest') as digest,patch.dict('sys.modules',{'torch':torch,'nemo':MagicMock(),'nemo.collections':MagicMock(),'nemo.collections.asr':MagicMock(),'nemo.collections.asr.models':api}):
            from memorybox.processing.voice_pilot import TITANET_SHA256
            digest.return_value.hexdigest.return_value=TITANET_SHA256
            self.assertIs(load_model('local.nemo'),model)
            api.EncDecSpeakerLabelModel.restore_from.assert_called_once_with(restore_path='local.nemo',map_location=torch.device.return_value)
            api.EncDecSpeakerLabelModel.from_pretrained.assert_not_called()
            model.cfg.preprocessor.sample_rate=8000
            with self.assertRaises(ValueError):load_model('local.nemo')
    def test_waveform_length_is_samples_not_relative_length(self):
        torch=MagicMock();model=MagicMock();signal=MagicMock();signal.numel.return_value=16000
        emb=MagicMock();model.forward.return_value=(None,emb)
        with patch.dict('sys.modules',{'torch':torch}):
            encode(model,signal)
            torch.tensor.assert_called_once_with([16000],dtype=torch.long)
            model.forward.assert_called_once_with(input_signal=signal.unsqueeze.return_value,input_signal_length=torch.tensor.return_value)

    def test_substitute_checkpoint_rejected(self):
        p=fixture();p['model']['sha256']='0'*64
        with self.assertRaises(ValueError):validate(p)
    def test_prepare_requires_explicit_thresholds(self):
        from memorybox.processing.voice_pilot_cli import main
        from contextlib import redirect_stderr
        import io
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            main(['prepare','--selection','test.json','--model','test.nemo','--revision','v1','--output','plan.json'])
        self.assertEqual(error.exception.code,2)
