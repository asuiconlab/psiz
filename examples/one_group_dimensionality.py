# -*- coding: utf-8 -*-
# Copyright 2020 The PsiZ Authors. All Rights Reserved.
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
# ==============================================================================

"""Example that infers an embedding with dimensionality regularizer.

Fake data is generated from a ground truth model assuming one group.
The Squeeze regularizer encourages solutions that use a relatively low
number of dimensions.

"""
import numpy as np
from sklearn.model_selection import StratifiedKFold
import tensorflow as tf
from tensorflow.python.keras import backend as K

import psiz

# Uncomment the following line to force eager execution.
# tf.config.experimental_run_functions_eagerly(True)


def main():
    """Run simulation."""
    # Settings.
    n_group = 1
    n_stimuli = 25
    n_dim_true = 3
    n_restart = 30
    n_dim_max = 30
    squeeze_rate = 1.

    emb_true = ground_truth(n_stimuli, n_dim_true)
    simmat_true = psiz.utils.similarity_matrix(emb_true.similarity, emb_true.z)

    # Generate a random docket of trials.
    n_trial = 5000
    n_reference = 8
    n_select = 2
    generator = psiz.generator.RandomGenerator(
        n_stimuli, n_reference=n_reference, n_select=n_select
    )
    docket = generator.generate(n_trial)

    # Simulate similarity judgments.
    agent = psiz.simulate.Agent(emb_true)
    obs = agent.simulate(docket)

    # Partition observations into train and test set.
    skf = StratifiedKFold(n_splits=10)
    (train_idx, test_idx) = list(
        skf.split(obs.stimulus_set, obs.config_idx)
    )[0]
    obs_train = obs.subset(train_idx)
    obs_test = obs.subset(test_idx)

    # Partition training observations into train and validation set.
    skf = StratifiedKFold(n_splits=10)
    (train_idx, val_idx) = list(
        skf.split(obs_train.stimulus_set, obs_train.config_idx)
    )[0]
    obs_train_train = obs_train.subset(train_idx)
    obs_val = obs_train.subset(val_idx)

    # Use early stopping.
    early_stop = psiz.keras.callbacks.EarlyStoppingRe(
        'val_loss', patience=10, mode='min', restore_best_weights=True
    )

    # Add regularization to embedding.
    reg = psiz.keras.regularizers.Squeeze(rate=squeeze_rate)

    # Infer embedding.
    embedding = psiz.keras.layers.EmbeddingRe(
        n_stimuli, n_dim=n_dim_max, embeddings_regularizer=reg
    )
    kernel = psiz.keras.layers.ExponentialKernel()
    rankModel = psiz.models.Rank(embedding=embedding, kernel=kernel)
    emb_inferred = psiz.models.Proxy(model=rankModel)
    emb_inferred.compile()
    restart_record = emb_inferred.fit(
        obs_train, validation_data=obs_val, epochs=1000, verbose=2,
        callbacks=[early_stop], n_restart=n_restart,
        monitor='val_loss'
    )

    # Compare the inferred model with ground truth by comparing the
    # similarity matrices implied by each model.
    simmat_infer = psiz.utils.similarity_matrix(
        emb_inferred.similarity, emb_inferred.z
    )
    r_squared = psiz.utils.matrix_comparison(
        simmat_true, simmat_infer, score='r2'
    )
    print("\n    r2: {0:.2f}".format(r_squared))

    # Analyze effective dimensionality.
    dimension_usage_mean = np.mean(np.abs(emb_inferred.z), axis=0)
    dimension_usage_max = np.max(np.abs(emb_inferred.z), axis=0)
    max_val = np.max(dimension_usage_max)
    idx_sorted = np.argsort(-dimension_usage_max)
    dimension_usage_mean = dimension_usage_mean[idx_sorted] / max_val
    dimension_usage_max = dimension_usage_max[idx_sorted] / max_val
    print(
        "    Proportion mean: {0}".format(
            np.array2string(
                dimension_usage_mean, formatter={'float_kind': lambda x: "%.3f" % x}
            )
        )
    )
    print(
        "    Proportion max: {0}".format(
            np.array2string(
                dimension_usage_max, formatter={'float_kind': lambda x: "%.3f" % x}
            )
        )
    )


def ground_truth(n_stimuli, n_dim):
    """Return a ground truth embedding."""
    kernel = psiz.keras.layers.ExponentialKernel()
    embedding = psiz.keras.layers.EmbeddingRe(n_stimuli, n_dim=n_dim)
    rankModel = psiz.models.Rank(embedding=embedding, kernel=kernel)
    emb = psiz.models.Proxy(rankModel)

    emb.theta = {
        'rho': 2.,
        'tau': 1.,
        'beta': 10.,
        'gamma': 0.001
    }

    mean = np.zeros((n_dim))
    cov = .03 * np.identity(n_dim)
    z = np.random.multivariate_normal(mean, cov, (n_stimuli))
    emb.z = z

    return emb


if __name__ == "__main__":
    main()