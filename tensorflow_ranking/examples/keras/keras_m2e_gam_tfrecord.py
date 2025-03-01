# Copyright 2022 The TensorFlow Ranking Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r"""TF-Ranking example code for training a Keras GAM model based estimator.

The supported proto formats are listed at ../python/data.py.
--------------------------------------------------------------------------------
Sample command lines:

MODEL_DIR=/tmp/output && \
TRAIN=tensorflow_ranking/examples/data/train_numerical_elwc.tfrecord && \
EVAL=tensorflow_ranking/examples/data/vali_numerical_elwc.tfrecord && \
rm -rf $MODEL_DIR && \
bazel build -c opt \
tensorflow_ranking/examples/keras/keras_m2e_gam_tfrecord_py_binary && \
./bazel-bin/tensorflow_ranking/examples/keras/keras_m2e_gam_tfrecord_py_binary \
--train_input_pattern=$TRAIN \
--eval_input_pattern=$EVAL \
--model_dir=$MODEL_DIR

You can use TensorBoard to display the training results stored in $MODEL_DIR.

Notes:
  * Use --alsologtostderr if the output is not printed into screen.
"""

from absl import flags

import tensorflow as tf
from tensorflow import estimator as tf_estimator
import tensorflow_ranking as tfr


flags.DEFINE_string("train_input_pattern", None,
                    "Input file path used for training.")
flags.DEFINE_string("eval_input_pattern", None,
                    "Input file path used for eval.")
flags.DEFINE_string("model_dir", None, "Output directory for models.")
flags.DEFINE_integer("batch_size", 32, "The batch size for train.")
flags.DEFINE_integer("num_train_steps", 15000, "Number of steps for train.")
flags.DEFINE_integer("num_eval_steps", 10, "Number of steps for evaluation.")
flags.DEFINE_integer("checkpoint_secs", 30,
                     "Saves a model checkpoint every checkpoint_secs seconds.")
flags.DEFINE_integer("num_checkpoints", 100,
                     "Saves at most num_checkpoints checkpoints in workspace.")

flags.DEFINE_integer("num_features", 136, "Number of features per example.")
flags.DEFINE_integer(
    "list_size", 100,
    "List size used for training. Use None for dynamic list size.")

flags.DEFINE_float("learning_rate", 0.05, "Learning rate for optimizer.")
flags.DEFINE_float("dropout", 0.5, "The dropout rate before output layer.")
flags.DEFINE_list("hidden_layer_dims", ["16", "8"],
                  "Sizes for hidden layers.")
flags.DEFINE_string("loss", "approx_ndcg_loss",
                    "The RankingLossKey for the loss function.")
flags.DEFINE_bool("convert_labels_to_binary", False,
                  "If true, relevance labels are set to either 0 or 1.")
flags.DEFINE_bool("listwise_inference", False,
                  "If true, exports ELWC while serving.")

FLAGS = flags.FLAGS

_LABEL_FEATURE = "utility"
_SIZE = "example_list_size"


def example_feature_columns():
  """Returns the example feature columns."""
  feature_names = [
      "custom_features_{}".format(i + 1) for i in range(FLAGS.num_features)
  ]
  return {
      name:
      tf.feature_column.numeric_column(name, shape=(1,), default_value=0.0)
      for name in feature_names
  }


def get_keras_estimator():
  """Returns a Keras based estimator for GAM ranking model."""
  network = tfr.keras.canned.GAMRankingNetwork(
      context_feature_columns=None,
      example_feature_columns=example_feature_columns(),
      example_hidden_layer_dims=FLAGS.hidden_layer_dims,
      activation=tf.nn.relu,
      dropout=FLAGS.dropout,
      use_batch_norm=True,
      batch_norm_moment=0.999,
      name="gam_ranking_network")
  loss = tfr.keras.losses.get(
      FLAGS.loss, reduction=tf.compat.v2.losses.Reduction.SUM_OVER_BATCH_SIZE)
  metrics = tfr.keras.metrics.default_keras_metrics()
  optimizer = tf.keras.optimizers.legacy.Adagrad(
      learning_rate=FLAGS.learning_rate)
  config = tf_estimator.RunConfig(
      model_dir=FLAGS.model_dir,
      keep_checkpoint_max=FLAGS.num_checkpoints,
      save_checkpoints_secs=FLAGS.checkpoint_secs)

  ranker = tfr.keras.model.create_keras_model(
      network=network,
      loss=loss,
      metrics=metrics,
      optimizer=optimizer,
      size_feature_name=_SIZE)
  return tfr.keras.estimator.model_to_estimator(
      model=ranker, model_dir=FLAGS.model_dir, config=config)


def train_and_eval():
  """Train and Evaluate."""
  estimator = get_keras_estimator()

  hparams = {
      "train_input_pattern": FLAGS.train_input_pattern,
      "eval_input_pattern": FLAGS.eval_input_pattern,
      "learning_rate": FLAGS.learning_rate,
      "train_batch_size": FLAGS.batch_size,
      "eval_batch_size": FLAGS.batch_size,
      "predict_batch_size": FLAGS.batch_size,
      "num_train_steps": FLAGS.num_train_steps,
      "num_eval_steps": FLAGS.num_eval_steps,
      "checkpoint_secs": FLAGS.checkpoint_secs,
      "num_checkpoints": FLAGS.num_checkpoints,
      "loss": FLAGS.loss,
      "list_size": FLAGS.list_size,
      "convert_labels_to_binary": FLAGS.convert_labels_to_binary,
      # Keras models only support listwise inference.
      "listwise_inference": True,
      "model_dir": FLAGS.model_dir
  }

  ranking_pipeline = tfr.ext.pipeline.RankingPipeline(
      {},
      example_feature_columns(),
      hparams,
      estimator=estimator,
      label_feature_name=_LABEL_FEATURE,
      label_feature_type=tf.int64,
      size_feature_name=_SIZE)

  ranking_pipeline.train_and_eval()


def main(_):
  tf.compat.v1.set_random_seed(1234)
  tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.INFO)
  train_and_eval()


if __name__ == "__main__":
  flags.mark_flag_as_required("train_input_pattern")
  flags.mark_flag_as_required("eval_input_pattern")
  flags.mark_flag_as_required("model_dir")

  tf.compat.v1.app.run()
