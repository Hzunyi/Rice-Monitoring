from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import cv2
from PIL import Image

def metric(correct_path, pred_path):
    correct = cv2.imread(correct_path, cv2.IMREAD_GRAYSCALE)
    pred = cv2.imread(pred_path, cv2.IMREAD_GRAYSCALE)

    correct = correct.reshape(-1)
    pred = pred.reshape(-1)


    precision = precision_score(correct, pred,zero_division=1)        #average='micro'
    recall = recall_score(correct, pred,zero_division=1)
    f1 = f1_score(correct, pred,zero_division=1)
    return precision, recall, f1

if __name__ == "__main__":

    precision, recall, f1 = metric(r'E:\PROGRAM\HZY400\result\label\label1.png',
                                   r'E:\PROGRAM\HZY400\result\ATTUNET\0.01\pingjie\ATTUNET_0.01_1.png') # 第一张为label，第二张为预测图片

    print(precision, recall, f1)