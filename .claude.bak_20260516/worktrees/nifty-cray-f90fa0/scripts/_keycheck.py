import numpy as np, os, sys
sys.path.insert(0, '/home/misterobots/bmo_client')
os.chdir('/home/misterobots/bmo_client')
from openwakeword.model import Model
m = Model(wakeword_model_paths=['/home/misterobots/bmo_client/hey_beeMo.onnx'])
pred = m.predict(np.zeros(1280, dtype=np.int16))
print('RAW KEYS:', list(pred.keys()))
print('RAW VALUES:', {k: float(v) for k, v in pred.items()})
