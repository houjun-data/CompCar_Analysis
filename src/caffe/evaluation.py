#!/usr/bin/env python

import os
import sys
import time
import argparse
import cPickle
import numpy as np
import scipy.io as sio

CAFFE_ROOT = '/home/lhy/Documents/Codes/Libs/caffe'
sys.path.insert(0, os.path.join(CAFFE_ROOT, 'python'))
import caffe

parser = argparse.ArgumentParser(description='Train a caffe model')
parser.add_argument('--gpu_id', dest='gpu_id',
                    help='GPU device to use [0]',
                    default=0, type=int)
parser.add_argument('--rank_num)', dest='rank_num',
                    help='rank num',
                    default=1, type=int)
parser.add_argument('--task', dest='task',
                    help='all front rear side front_side rear_side',
                    default='all', type=str)
parser.add_argument('--level', dest='level',
                    help='make model',
                    default='make', type=str)
args = parser.parse_args()

if args.task == 'all':
    task_str = ''
else:
    task_str = '_'+args.task
level_str = '_'+args.level
solver_prototxt = 'models/compcar'+task_str+level_str+'/solver.prototxt'
model_files = os.listdir(os.path.join('models',
                                      'compcar'+task_str+level_str))
model_files = filter(lambda s: s[-11:] == '.caffemodel', model_files)
pretrained_model = model_files[-1]


if not os.path.exists('./data'):
    os.mkdir('data')

res_file = 'cache/'+task_str+level_str+'_det_res.pkl'
DATA_ROOT = 'data'
im_list_file = 'data/train_test_split/classification/test'+task_str+level_str+'.txt'

CONF_THRESHOLD = 0.3

with open(im_list_file) as fd:
    gt = map(lambda s: s.strip().split(' '), fd.readlines())

make_model_name = sio.loadmat(os.path.join(DATA_ROOT, 'misc', 'make_model_name.mat'), squeeze_me = True)
makes = make_model_name['make_names'].tolist()
raw_models = make_model_name['model_names'].tolist()
filter_ids = filter(lambda i: isinstance(raw_models[i], unicode) or isinstance(raw_models[i], str), range(len(raw_models)))
filter_ids = [x+1 for x in filter_ids]
if args.level == 'make':
    CLASS_NUM = len(makes)
elif args.level == 'model':
    CLASSES_NUM = len(filter_ids)


if os.path.exists(res_file):
    with open(res_file, 'rb') as fd:
        det_res = cPickle.load(fd)
        # print '\nLoaded det_files\n'
else:
    caffe.set_device(args.gpu_id)
    caffe.set_mode_gpu()
    net = caffe.Classifier(solver_prototxt,
                           pretrained_model,
                           channel_swap=(2, 1, 0),
                           raw_scale=255,
                           image_dims=(224, 224))
    print '\nLoaded network {:s}'.format(pretrained_model)

    det_res = []
    for img, label in gt:
        im = caffe.io.load_image(os.path.join(DATA_ROOT, 'cropped_image', img))
        t1 = time.time()
        pred = net.predict([im])[0]
        t2 = time.time()
        print 'finish processing %s in %f s' % (img, t2-t1)
        y = np.argsort(-pred)
        ids = pred[y] > CONF_THRESHOLD
        det_res.append([img, int(label), y[ids], pred[y][ids]])
    with open(res_file, 'wb') as fd:
        cPickle.dump(det_res, fd, cPickle.HIGHEST_PROTOCOL)
    print '\n\nwrote results to %s\n' % res_file

total_hit_num = 0
total_num = len(det_res)
hit_num = np.zeros([CLASS_NUM, ])
num = np.zeros([CLASS_NUM, ])
for img, label, y, scores in det_res:
    n_pred = y.shape[0]
    num[int(label)-1] += 1
    if np.any(y[:min(n_pred, args.rank_num)] == int(label)):
        total_hit_num += 1
        hit_num[int(label)-1] += 1

print 'rank %d average recognition rate = %f(%d/%d)\n' % (args.rank_num, 1.0*total_hit_num/total_num, total_hit_num, total_num)
