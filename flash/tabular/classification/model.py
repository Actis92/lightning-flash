# Copyright The PyTorch Lightning team.
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
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Type

from torch.nn import functional as F

from flash.core.classification import ClassificationAdapterTask
from flash.core.data.io.input import ServeInput
from flash.core.data.io.input_transform import InputTransform
from flash.core.integrations.pytorch_tabular.backbones import PYTORCH_TABULAR_BACKBONES
from flash.core.registry import FlashRegistry
from flash.core.serve import Composition
from flash.core.utilities.imports import requires
from flash.core.utilities.types import INPUT_TRANSFORM_TYPE, LR_SCHEDULER_TYPE, METRICS_TYPE, OPTIMIZER_TYPE
from flash.tabular.input import TabularDeserializer


class TabularClassifier(ClassificationAdapterTask):
    """The ``TabularClassifier`` is a :class:`~flash.Task` for classifying tabular data. For more details, see
    :ref:`tabular_classification`.

    Args:
        embedding_sizes: Number of columns in table (not including target column).
        categorical_fields: Number of classes to classify.
        embedding_sizes: List of (num_classes, emb_dim) to form categorical embeddings.
        cat_dims: Number of distinct values for each categorical column
        num_features: Number of columns in table
        num_classes: Number of classes to classify
        backbone: name of the model to use
        loss_fn: Loss function for training, defaults to cross entropy.
        optimizer: Optimizer to use for training.
        lr_scheduler: The LR scheduler to use during training.
        metrics: Metrics to compute for training and evaluation. Can either be an metric from the `torchmetrics`
            package, a custom metric inherenting from `torchmetrics.Metric`, a callable function or a list/dict
            containing a combination of the aforementioned. In all cases, each metric needs to have the signature
            `metric(preds,target)` and return a single scalar tensor. Defaults to :class:`torchmetrics.Accuracy`.
        learning_rate: Learning rate to use for training.
        **backbone_kwargs: Optional additional arguments for the model.
    """

    required_extras: str = "tabular"
    backbones: FlashRegistry = FlashRegistry("backbones") + PYTORCH_TABULAR_BACKBONES

    def __init__(
        self,
        embedding_sizes: list,
        categorical_fields: list,
        cat_dims: list,
        num_features: int,
        num_classes: int,
        backbone: str = "tabnet",
        loss_fn: Callable = F.cross_entropy,
        optimizer: OPTIMIZER_TYPE = "Adam",
        lr_scheduler: LR_SCHEDULER_TYPE = None,
        metrics: METRICS_TYPE = None,
        learning_rate: float = 5e-4,
        **backbone_kwargs,
    ):
        self.save_hyperparameters()
        metadata = self.backbones.get(backbone, with_metadata=True)
        adapter = metadata["metadata"]["adapter"].from_task(
            self,
            task_type="classification",
            embedding_sizes=embedding_sizes,
            categorical_fields=categorical_fields,
            cat_dims=cat_dims,
            num_features=num_features,
            output_dim=num_classes,
            backbone=backbone,
            backbone_kwargs=backbone_kwargs,
            loss_fn=loss_fn,
            metrics=metrics,
        )
        super().__init__(
            adapter,
            optimizer=optimizer,
            lr_scheduler=lr_scheduler,
            learning_rate=learning_rate,
        )

    @staticmethod
    def _ci_benchmark_fn(history: List[Dict[str, Any]]):
        """This function is used only for debugging usage with CI."""
        assert history[-1]["valid_accuracy"] > 0.6, history[-1]["valid_accuracy"]

    @classmethod
    def from_data(cls, datamodule, **kwargs) -> "TabularClassifier":
        model = cls(
            embedding_sizes=datamodule.embedding_sizes,
            categorical_fields=datamodule.categorical_fields,
            cat_dims=datamodule.cat_dims,
            num_features=datamodule.num_features,
            num_classes=datamodule.num_classes,
            **kwargs,
        )
        return model

    @requires("serve")
    def serve(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        sanity_check: bool = True,
        input_cls: Optional[Type[ServeInput]] = TabularDeserializer,
        transform: INPUT_TRANSFORM_TYPE = InputTransform,
        transform_kwargs: Optional[Dict] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Composition:
        return super().serve(
            host, port, sanity_check, partial(input_cls, parameters=parameters), transform, transform_kwargs
        )
