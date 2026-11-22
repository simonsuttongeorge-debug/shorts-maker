import numpy as np, mediapipe as mp, os
from mediapipe.tasks.python import vision, BaseOptions
_M=os.path.join(os.path.dirname(__file__),'..','models','selfie_multiclass.tflite')
class Seg:
    def __init__(self):
        o=vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=_M),running_mode=vision.RunningMode.IMAGE,output_confidence_masks=True)
        self.s=vision.ImageSegmenter.create_from_options(o)
    def person(self,rgb):
        r=self.s.segment(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb)))
        bg=r.confidence_masks[0].numpy_view()
        return np.clip(1.0-np.squeeze(bg),0,1).astype(np.float32)  # person prob
