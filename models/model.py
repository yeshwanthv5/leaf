"""Interfaces for ClientModel and ServerModel."""

from abc import ABC, abstractmethod
import numpy as np
import os
import sys
import tensorflow as tf

from baseline_constants import ACCURACY_KEY

from utils.model_utils import batch_data
from utils.tf_utils import graph_size

from tensorflow.python.tools import inspect_checkpoint as inch

class Model(ABC):

    def __init__(self, seed, lr, optimizer=None, checkpoint_dir=None):
        self.lr = lr
        self.seed = seed
        self._optimizer = optimizer

        self.graph = tf.Graph()
        with self.graph.as_default() as g:
            tf.set_random_seed(123 + self.seed)
            self.features, self.labels, self.train_op, self.eval_metric_ops, self.loss = self.create_model()
            self.saver = tf.train.Saver(var_list={"conv1/bias/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("conv2d/bias:0"),"conv2/bias/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("conv2d_1/bias:0"),"conv2/kernel/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("conv2d_1/kernel:0"), "d1/bias/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("dense/bias:0")})
            # self.saver = tf.train.Saver(var_list={"conv1/bias/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("conv2d/bias:0"), "conv1/kernel/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("conv2d/kernel:0"),"conv2/bias/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("conv2d_1/bias:0"),"conv2/kernel/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("conv2d_1/kernel:0"), "d1/bias/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("dense/bias:0"), "d1/kernel/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("dense/kernel:0"), "d2/bias/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("dense_1/bias:0"), "d2/kernel/.ATTRIBUTES/VARIABLE_VALUE": g.get_tensor_by_name("dense_1/kernel:0")})
            # self.saver = tf.train.Saver()
        self.sess = tf.Session(graph=self.graph)

        self.size = graph_size(self.graph)

        with self.graph.as_default() as g:
            self.sess.run(tf.global_variables_initializer())
            if checkpoint_dir != None:
                variables_in_checkpoint = tf.train.list_variables('./checkpoint/my_checkpoint')
                print("Variables found in checkpoint file",variables_in_checkpoint)
                all_vars = tf.global_variables()
                print(all_vars)
                print(g.get_tensor_by_name("conv2d/kernel:0"))
                # exit()
                self.saver.restore(self.sess,tf.train.latest_checkpoint(checkpoint_dir))

            metadata = tf.RunMetadata()
            opts = tf.profiler.ProfileOptionBuilder.float_operation()
            self.flops = tf.profiler.profile(self.graph, run_meta=metadata, cmd='scope', options=opts).total_float_ops

        np.random.seed(self.seed)

    def set_params(self, model_params):
        with self.graph.as_default():
            all_vars = tf.trainable_variables()
            for variable, value in zip(all_vars, model_params):
                variable.load(value, self.sess)

    def get_params(self):
        with self.graph.as_default():
            model_params = self.sess.run(tf.trainable_variables())
        return model_params

    @property
    def optimizer(self):
        """Optimizer to be used by the model."""
        if self._optimizer is None:
            self._optimizer = tf.train.GradientDescentOptimizer(learning_rate=self.lr)

        return self._optimizer

    @abstractmethod
    def create_model(self):
        """Creates the model for the task.

        Returns:
            A 4-tuple consisting of:
                features: A placeholder for the samples' features.
                labels: A placeholder for the samples' labels.
                train_op: A Tensorflow operation that, when run with the features and
                    the labels, trains the model.
                eval_metric_ops: A Tensorflow operation that, when run with features and labels,
                    returns the accuracy of the model.
        """
        return None, None, None, None, None

    def train(self, data, num_epochs=1, batch_size=10):
        """
        Trains the client model.

        Args:
            data: Dict of the form {'x': [list], 'y': [list]}.
            num_epochs: Number of epochs to train.
            batch_size: Size of training batches.
        Return:
            comp: Number of FLOPs computed while training given data
            update: List of np.ndarray weights, with each weight array
                corresponding to a variable in the resulting graph
        """
        for _ in range(num_epochs):
            self.run_epoch(data, batch_size)

        update = self.get_params()
        comp = num_epochs * (len(data['y'])//batch_size) * batch_size * self.flops
        return comp, update

    def run_epoch(self, data, batch_size):

        for batched_x, batched_y in batch_data(data, batch_size, seed=self.seed):
            
            input_data = self.process_x(batched_x)
            target_data = self.process_y(batched_y)
            
            with self.graph.as_default():
                self.sess.run(self.train_op,
                    feed_dict={
                        self.features: input_data,
                        self.labels: target_data
                    })

    def test(self, data):
        """
        Tests the current model on the given data.

        Args:
            data: dict of the form {'x': [list], 'y': [list]}
        Return:
            dict of metrics that will be recorded by the simulation.
        """
        x_vecs = self.process_x(data['x'])
        labels = self.process_y(data['y'])
        with self.graph.as_default():
            tot_acc, loss = self.sess.run(
                [self.eval_metric_ops, self.loss],
                feed_dict={self.features: x_vecs, self.labels: labels}
            )
        acc = float(tot_acc) / x_vecs.shape[0]
        return {ACCURACY_KEY: acc, 'loss': loss}

    def close(self):
        self.sess.close()

    @abstractmethod
    def process_x(self, raw_x_batch):
        """Pre-processes each batch of features before being fed to the model."""
        pass

    @abstractmethod
    def process_y(self, raw_y_batch):
        """Pre-processes each batch of labels before being fed to the model."""
        pass


class ServerModel:
    def __init__(self, model):
        self.model = model

    @property
    def size(self):
        return self.model.size

    @property
    def cur_model(self):
        return self.model

    def send_to(self, clients):
        """Copies server model variables to each of the given clients

        Args:
            clients: list of Client objects
        """
        var_vals = {}
        with self.model.graph.as_default():
            all_vars = tf.trainable_variables()
            for v in all_vars:
                val = self.model.sess.run(v)
                var_vals[v.name] = val
        for c in clients:
            with c.model.graph.as_default():
                all_vars = tf.trainable_variables()
                for v in all_vars:
                    v.load(var_vals[v.name], c.model.sess)

    def save(self, path='checkpoints/model.ckpt'):
        return self.model.saver.save(self.model.sess, path)

    def close(self):
        self.model.close()
