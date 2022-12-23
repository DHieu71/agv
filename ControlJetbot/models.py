from torch2trt import TRTModule
class Models:
    def __init__(self) -> None:
        self.models = TRTModule()
        self.mean = torch.Tensor([0.485, 0.456, 0.406]).cuda().half()
        self.std = torch.Tensor([0.229, 0.224, 0.225]).cuda().half()
        self.device = torch.device('cuda')
        
    def loadModel(self, fileDir) -> None:
        self.models = self.models.load_state_dict(torch.load('fileDir'))
        
    def __preprocess(self, frame):
        frame = PIL.Image.fromarray(frame)
        frame = transforms.functional.to_tensor(frame).to(self.device).half()
        frame.sub_(self.mean[:, None, None]).div_(self.std[:, None, None])
        return frame[None, ...]
    
    def process(self, image):
        xy = self.models(self.__preprocess(image)).detach().float().cpu().numpy().flatten()
        x = xy[0]
        y = (0.5 - xy[1]) / 2.0
        angle = np.arctan2(x, y)
        pid = angle * steering_gain_slider + (angle - angle_last) * steering_dgain_slider
        angle_last = angle
        steering_slider = pid + steering_bias_slider
        
