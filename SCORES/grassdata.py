import torch
from torch.utils import data
from scipy.io import loadmat
from enum import Enum
import os
import json
import numpy as np

class Tree(object):
    class NodeType(Enum):
        BOX = 0  # box node
        ADJ = 1  # adjacency (adjacent part assembly) node
        SYM = 2  # symmetry (symmetric part grouping) node

    class Node(object):
        def __init__(self, box=None, left=None, right=None, node_type=None, sym=None, label=None, objname=None):
            self.box = box          # box feature vector for a leaf node
            self.sym = sym          # symmetry parameter vector for a symmetry node
            self.left = left        # left child for ADJ or SYM (a symmeter generator)
            self.right = right      # right child
            self.node_type = node_type
            self.label = label
            self.objname = objname

        def is_leaf(self):
            return self.node_type == Tree.NodeType.BOX and self.box is not None

        def is_adj(self):
            return self.node_type == Tree.NodeType.ADJ

        def is_sym(self):
            return self.node_type == Tree.NodeType.SYM

    def __init__(self, boxes, ops, syms, labels, objname):
        box_list = [b for b in torch.split(boxes, 1, 0)]
        sym_param = [s for s in torch.split(syms, 1, 0)]
        label_list = [l for l in labels[0]]
        box_list.reverse()
        sym_param.reverse()
        label_list.reverse()
        objname.reverse()
        queue = []
        for id in range(ops.size()[1]):
            if ops[0, id] == Tree.NodeType.BOX.value:
                queue.append(Tree.Node(box=box_list.pop(), node_type=Tree.NodeType.BOX, label=label_list.pop(), objname=objname.pop()))
            elif ops[0, id] == Tree.NodeType.ADJ.value:
                left_node = queue.pop()
                right_node = queue.pop()
                queue.append(Tree.Node(left=left_node, right=right_node, node_type=Tree.NodeType.ADJ))
            elif ops[0, id] == Tree.NodeType.SYM.value:
                node = queue.pop()
                queue.append(Tree.Node(left=node, sym=sym_param.pop(), node_type=Tree.NodeType.SYM))
        assert len(queue) == 1
        self.root = queue[0]

def rotate_boxes(boxes, syms):
    new_boxes = torch.zeros(boxes.shape)
    for k in range(boxes.shape[0]):
        new_boxes[k, 0] = boxes[k, 2]
        new_boxes[k, 1] = boxes[k, 1]
        new_boxes[k, 2] = -boxes[k, 0]

        new_boxes[k, 3] = boxes[k, 3]
        new_boxes[k, 4] = boxes[k, 5]
        new_boxes[k, 5] = boxes[k, 4]

        new_boxes[k, 6] = boxes[k, 6]
        new_boxes[k, 7] = boxes[k, 7]
        new_boxes[k, 8] = boxes[k, 8]

        new_boxes[k, 9] = boxes[k, 9]
        new_boxes[k, 10] = boxes[k, 10]
        new_boxes[k, 11] = boxes[k, 11]

    # rotate syms
    new_syms = torch.zeros(syms.shape)
    for k in range(syms.shape[0]):
        new_syms[k, 0] = syms[k, 0]

        new_syms[k, 1] = syms[k, 3]
        new_syms[k, 2] = syms[k, 2]
        new_syms[k, 3] = -syms[k, 1]

        new_syms[k, 4] = syms[k, 6]
        new_syms[k, 5] = syms[k, 5]
        new_syms[k, 6] = -syms[k, 4]

        new_syms[k, 7] = syms[k, 7]
    return new_boxes, new_syms


class GRASSDataset(data.Dataset,):
    def __init__(self, dir_syms, dir_objs, models_num=0, transform=None):
        self.dir = dir_syms
        num_examples = len(os.listdir(os.path.join(dir_syms, 'ops')))
        self.transform = transform
        self.trees = []
        self.Ids = []
        self.orgTrees = []

        for i in range(models_num):
            boxes = torch.from_numpy(loadmat(os.path.join(dir_syms, 'boxes', '%d.mat' % (i+1)))['box']).t().float()
            ops = torch.from_numpy(loadmat(os.path.join(dir_syms, 'ops', '%d.mat' % (i+1)))['op']).int()
            syms = torch.from_numpy(loadmat(os.path.join(dir_syms, 'syms', '%d.mat' % (i+1)))['sym']).t().float()
            labels = torch.from_numpy(loadmat(os.path.join(dir_syms, 'labels', '%d.mat' % (i+1)))['label']).int()
            shapeId = loadmat(os.path.join(dir_syms, 'part mesh indices', '%d.mat' % (i+1)))['shapename'].item()
            objcorrespondence = loadmat(os.path.join(dir_syms, 'part mesh indices', '%d.mat' % (i+1)))['cell_boxs_correspond_objSerialNumber'][0]

            json_file = open(os.path.join(dir_objs,shapeId,'result_after_merging.json'), 'r')
            json_content = json.load(json_file)
            json_file.close()
            originalobjsloc = json_content[0]['objs']

            objnames = []
            for box in objcorrespondence:
                box_objs = []
                for index in box[0]:
                    box_objs.append(shapeId+'/objs/'+originalobjsloc[index-1]+'.obj')
                objnames.append(box_objs)

            new_boxes1, new_syms1 = rotate_boxes(boxes, syms)
            orgTree = Tree(boxes, ops.clone(), syms, labels.clone(), objnames.copy())
            tree = Tree(new_boxes1, ops, new_syms1, labels, objnames)

            self.trees.append(tree)
            self.orgTrees.append(orgTree)
            self.Ids.append(shapeId)

    def __getitem__(self, index):
        tree = self.trees[index]
        return tree

    def __len__(self):
        return len(self.trees)