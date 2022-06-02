import os
import sys
import torch
import cv2
import numpy as np
import torch.nn as nn
import torchvision.utils as vutils
from utils import decode_segmap
from SegDataFolder import semData
from getSetting import get_yaml, get_criterion, get_optim, get_scheduler, get_net
from metric import AverageMeter, intersectionAndUnion
from tensorboardX import SummaryWriter
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, precision_recall_curve


# for transform
# 需要计算文件夹对应图片的mean&std，或者使用trainset的mean std
mean = np.array([0.0734, 2.3987e-04, 1.6012e-04, 0.0138, 18.1685,  0.6454,  0.6546,
                       0.0806, -1.0369e-04, 9.0466e-05, 0.0134, 14.9679,  0.7128,  0.5824,
                       0.1295, -1.3386e-04,  -1.6145e-04,  0.0223,  15.5970,  0.6984, 0.6007,
                       0.1059, 3.4484e-04,  -1.8908e-04,  0.0255,  20.8862, 0.5880,  0.7235,
                       0.1380, 0.0015, 4.4528e-04, 0.0352, 20.8000, 0.5963, 0.7186])       # 训练原图的平均值
std = np.array([0.1819, 0.0298, 0.0291, 0.0246, 5.8932,  0.1246,  0.1380,
                      0.2170, 0.0390, 0.0366, 0.0292, 4.3461, 0.0869, 0.1114,
                      0.2306, 0.0351, 0.0375, 0.0286, 4.3605, 0.0892, 0.1092,
                      0.2168, 0.0385, 0.0380, 0.0318, 4.6144, 0.0966, 0.0932,
                      0.2347, 0.0378, 0.0384,  0.0341, 3.9631, 0.0785, 0.0791])               # 训练原图的方差

def get_idx(channels):
    assert channels in [2, 4, 35]
    if channels == 35:
        return list(range(35))
    elif channels == 4:
        return list(range(4))
    elif channels == 2:
        return list(range(6))[-2:]

def getTransorm4eval(channel_idx=[0,1,2,3]):
    import transform as T
    return T.Compose(
        [
            T.ToTensor(),
            T.Normalize(mean=mean[channel_idx],std=std[channel_idx])
        ]
    )

def eval(args,config,):
    os.makedirs(args.outputdir, exist_ok=True)

    net = get_net(config) 
    softmax = nn.Softmax(dim=1)
    # load checkpoint
    checkpoint = torch.load(args.checkpoint)
    net.load_state_dict(checkpoint['net'])
    net = net.cuda() if args.use_gpu else net

    dataset = semData(
        train=False,
        root='./Data',
        channels = config['channels'],
        transform=getTransorm4eval(channel_idx=get_idx(config['channels'])),
        selftest_dir=args.testdir
    )
    dataloader = torch.utils.data.DataLoader(dataset, 1, shuffle=False)
    
    net.eval()
    with torch.no_grad():
        intersection_meter = AverageMeter()
        union_meter = AverageMeter()
        target_meter = AverageMeter()
        correct = []
        preds = []



        for i, batch in enumerate(dataloader):
            img = batch['X'].cuda() if args.use_gpu else batch['X']
            label = batch['Y'].cuda() if args.use_gpu else batch['Y']
            path = batch['path'][0].split('.')[0]

            outp = net(img)
            
            score = softmax(outp)      
            pred = score.max(1)[1]

            saved_1 = pred.squeeze().cpu().numpy()
            saved_255 = 255 * saved_1

            # 保存预测图片，像素值为0&1
            cv2.imwrite('eval_output/eval_output_1/{}.png'.format(path), saved_1, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            # 保存预测图片，像素值为0&255
            cv2.imwrite('eval_output/eval_output_255/{}.png'.format(path), saved_255, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            
            correct.extend(label.reshape(-1).cpu().numpy())
            preds.extend(pred.reshape(-1).cpu().numpy())
            
            N = img.size()[0]
            
            intersection, union, target = intersectionAndUnion(pred.cpu().numpy(), label.cpu().numpy(), config['n_classes'], config['ignore_index'])
            intersection_meter.update(intersection), union_meter.update(union), target_meter.update(target)

            acc = sum(intersection_meter.val) / (sum(target_meter.val) + 1e-10)

        
        iou_class = intersection_meter.sum / (union_meter.sum + 1e-10)
        acc_class = intersection_meter.sum / (target_meter.sum + 1e-10)
        mIoU = np.mean(iou_class)
        mAcc = np.mean(acc_class)
        allAcc = sum(intersection_meter.sum) / (sum(target_meter.sum)+1e-10)
        precision = precision_score(correct, preds)
        recall = recall_score(correct, preds)
        f1 = f1_score(correct, preds)

        print('mIoU {:.4f} | mAcc {:.4f} | allAcc {:.4f} | precision {:.4f} | recall {:.4f} | f1 {:.4f}'.format(
            mIoU, mAcc, allAcc, precision, recall, f1
        ))

        

### argument parse
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--testdir',type=str,default='eval', help='path of test images') # 测试文件夹，需要放在Data文件夹下，跟train,test有相同结构
parser.add_argument('--outputdir',type=str,default='eval_output',help='test output') # 指定生成预测图片的输出文件夹
parser.add_argument('--gpu',type=int, default=0,help='gpu index to run') # gpu卡号，单卡默认为0
parser.add_argument('--configfile',type=str, default='ConfigFiles/config-deeplab.yaml',help='path to config files') # 选定configfile,用于指定网络
parser.add_argument('--checkpoint',type=str, default='eventfiles-deeplab-channels7-SGD-bs=6-lr=0.001/DeepLab-0.8284-ep7.pth', help='checkpoint path') # 加载定模型路径
args = parser.parse_args()

if __name__ == "__main__":
    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu)
    if torch.cuda.is_available():
        args.use_gpu = True
    else:
        args.use_gpu = False
    
    config = get_yaml(args.configfile)
    eval(args, config)


