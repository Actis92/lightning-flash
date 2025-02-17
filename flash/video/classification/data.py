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
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

import pandas as pd
import torch
from torch.utils.data import Sampler

from flash.core.data.data_module import DataModule
from flash.core.data.data_pipeline import DataPipelineState
from flash.core.data.io.input import Input
from flash.core.data.io.input_transform import INPUT_TRANSFORM_TYPE
from flash.core.data.utilities.paths import PATH_TYPE
from flash.core.integrations.labelstudio.input import _parse_labelstudio_arguments, LabelStudioVideoClassificationInput
from flash.core.utilities.imports import _FIFTYONE_AVAILABLE, _PYTORCHVIDEO_AVAILABLE, _VIDEO_AVAILABLE, requires
from flash.core.utilities.stages import RunningStage
from flash.video.classification.input import (
    VideoClassificationCSVInput,
    VideoClassificationCSVPredictInput,
    VideoClassificationDataFrameInput,
    VideoClassificationDataFramePredictInput,
    VideoClassificationFiftyOneInput,
    VideoClassificationFilesInput,
    VideoClassificationFoldersInput,
    VideoClassificationPathsPredictInput,
)
from flash.video.classification.input_transform import VideoClassificationInputTransform

if _FIFTYONE_AVAILABLE:
    SampleCollection = "fiftyone.core.collections.SampleCollection"
else:
    SampleCollection = None

if _PYTORCHVIDEO_AVAILABLE:
    from pytorchvideo.data.clip_sampling import ClipSampler
else:
    ClipSampler = None

# Skip doctests if requirements aren't available
if not _VIDEO_AVAILABLE:
    __doctest_skip__ = ["VideoClassificationData", "VideoClassificationData.*"]


class VideoClassificationData(DataModule):
    """The ``VideoClassificationData`` class is a :class:`~flash.core.data.data_module.DataModule` with a set of
    classmethods for loading data for video classification."""

    input_transform_cls = VideoClassificationInputTransform

    @classmethod
    def from_files(
        cls,
        train_files: Optional[Sequence[str]] = None,
        train_targets: Optional[Sequence[Any]] = None,
        val_files: Optional[Sequence[str]] = None,
        val_targets: Optional[Sequence[Any]] = None,
        test_files: Optional[Sequence[str]] = None,
        test_targets: Optional[Sequence[Any]] = None,
        predict_files: Optional[Sequence[str]] = None,
        train_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        val_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        test_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        predict_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
        input_cls: Type[Input] = VideoClassificationFilesInput,
        predict_input_cls: Type[Input] = VideoClassificationPathsPredictInput,
        transform_kwargs: Optional[Dict] = None,
        **data_module_kwargs,
    ) -> "VideoClassificationData":
        """Load the :class:`~flash.video.classification.data.VideoClassificationData` from lists of files and
        corresponding lists of targets.

        The supported file extensions are: ``.mp4``, and ``.avi``.
        The targets can be in any of our
        :ref:`supported classification target formats <formatting_classification_targets>`.
        To learn how to customize the transforms applied for each stage, read our
        :ref:`customizing transforms guide <customizing_transforms>`.

        Args:
            train_files: The list of video files to use when training.
            train_targets: The list of targets to use when training.
            val_files: The list of video files to use when validating.
            val_targets: The list of targets to use when validating.
            test_files: The list of video files to use when testing.
            test_targets: The list of targets to use when testing.
            predict_files: The list of video files to use when predicting.
            train_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when training.
            val_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when validating.
            test_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when testing.
            predict_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when
                predicting.
            clip_sampler: The clip sampler to use. One of: ``"uniform"``, ``"random"``, ``"constant_clips_per_video"``.
            clip_duration: The duration of clips to sample.
            clip_sampler_kwargs: Additional keyword arguments to use when constructing the clip sampler.
            video_sampler: Sampler for the internal video container. This defines the order videos are decoded and,
                if necessary, the distributed split.
            decode_audio: If True, also decode audio from video.
            decoder: The decoder to use to decode videos. One of: ``"pyav"``, ``"torchvision"``. Not used for frame
                videos.
            input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the data.
            predict_input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the prediction data.
            transform_kwargs: Dict of keyword arguments to be provided when instantiating the transforms.
            data_module_kwargs: Additional keyword arguments to provide to the
                :class:`~flash.core.data.data_module.DataModule` constructor.

        Returns:
            The constructed :class:`~flash.video.classification.data.VideoClassificationData`.

        Examples
        ________

        .. testsetup::

            >>> import torch
            >>> from torchvision import io
            >>> data = torch.randint(255, (10, 64, 64, 3))
            >>> _ = [io.write_video(f"video_{i}.mp4", data, 5, "libx264rgb", {"crf": "0"}) for i in range(1, 4)]
            >>> _ = [io.write_video(f"predict_video_{i}.mp4", data, 5, "libx264rgb", {"crf": "0"}) for i in range(1, 4)]

        .. doctest::

            >>> from flash import Trainer
            >>> from flash.video import VideoClassifier, VideoClassificationData
            >>> datamodule = VideoClassificationData.from_files(
            ...     train_files=["video_1.mp4", "video_2.mp4", "video_3.mp4"],
            ...     train_targets=["cat", "dog", "cat"],
            ...     predict_files=["predict_video_1.mp4", "predict_video_2.mp4", "predict_video_3.mp4"],
            ...     transform_kwargs=dict(image_size=(244, 244)),
            ...     batch_size=2,
            ... )
            >>> datamodule.num_classes
            2
            >>> datamodule.labels
            ['cat', 'dog']
            >>> model = VideoClassifier(backbone="x3d_xs", num_classes=datamodule.num_classes)
            >>> trainer = Trainer(fast_dev_run=True)
            >>> trainer.fit(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Training...
            >>> trainer.predict(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Predicting...

        .. testcleanup::

            >>> import os
            >>> _ = [os.remove(f"video_{i}.mp4") for i in range(1, 4)]
            >>> _ = [os.remove(f"predict_video_{i}.mp4") for i in range(1, 4)]
        """

        ds_kw = dict(
            data_pipeline_state=DataPipelineState(),
            transform_kwargs=transform_kwargs,
            input_transforms_registry=cls.input_transforms_registry,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )

        return cls(
            input_cls(RunningStage.TRAINING, train_files, train_targets, transform=train_transform, **ds_kw),
            input_cls(RunningStage.VALIDATING, val_files, val_targets, transform=val_transform, **ds_kw),
            input_cls(RunningStage.TESTING, test_files, test_targets, transform=test_transform, **ds_kw),
            predict_input_cls(RunningStage.PREDICTING, predict_files, transform=predict_transform, **ds_kw),
            **data_module_kwargs,
        )

    @classmethod
    def from_folders(
        cls,
        train_folder: Optional[str] = None,
        val_folder: Optional[str] = None,
        test_folder: Optional[str] = None,
        predict_folder: Optional[str] = None,
        train_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        val_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        test_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        predict_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
        input_cls: Type[Input] = VideoClassificationFoldersInput,
        predict_input_cls: Type[Input] = VideoClassificationPathsPredictInput,
        transform_kwargs: Optional[Dict] = None,
        **data_module_kwargs,
    ) -> "VideoClassificationData":
        """Load the :class:`~flash.video.classification.data.VideoClassificationData` from folders containing
        videos.

        The supported file extensions are: ``.mp4``, and ``.avi``.
        For train, test, and validation data, the folders are expected to contain a sub-folder for each class.
        Here's the required structure:

        .. code-block::

            train_folder
            ├── cat
            │   ├── video_1.mp4
            │   ├── video_3.mp4
            │   ...
            └── dog
                ├── video_2.mp4
                ...

        For prediction, the folder is expected to contain the files for inference, like this:

        .. code-block::

            predict_folder
            ├── predict_video_1.mp4
            ├── predict_video_2.mp4
            ├── predict_video_3.mp4
            ...

        To learn how to customize the transforms applied for each stage, read our
        :ref:`customizing transforms guide <customizing_transforms>`.

        Args:
            train_folder: The folder containing videos to use when training.
            val_folder: The folder containing videos to use when validating.
            test_folder: The folder containing videos to use when testing.
            predict_folder: The folder containing videos to use when predicting.
            train_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when training.
            val_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when validating.
            test_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when testing.
            predict_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when
                predicting.
            clip_sampler: The clip sampler to use. One of: ``"uniform"``, ``"random"``, ``"constant_clips_per_video"``.
            clip_duration: The duration of clips to sample.
            clip_sampler_kwargs: Additional keyword arguments to use when constructing the clip sampler.
            video_sampler: Sampler for the internal video container. This defines the order videos are decoded and,
                if necessary, the distributed split.
            decode_audio: If True, also decode audio from video.
            decoder: The decoder to use to decode videos. One of: ``"pyav"``, ``"torchvision"``. Not used for frame
                videos.
            input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the data.
            predict_input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the prediction data.
            transform_kwargs: Dict of keyword arguments to be provided when instantiating the transforms.
            data_module_kwargs: Additional keyword arguments to provide to the
                :class:`~flash.core.data.data_module.DataModule` constructor.

        Returns:
            The constructed :class:`~flash.video.classification.data.VideoClassificationData`.

        Examples
        ________

        .. testsetup::

            >>> import os
            >>> import torch
            >>> from torchvision import io
            >>> data = torch.randint(255, (10, 64, 64, 3))
            >>> os.makedirs(os.path.join("train_folder", "cat"), exist_ok=True)
            >>> os.makedirs(os.path.join("train_folder", "dog"), exist_ok=True)
            >>> os.makedirs("predict_folder", exist_ok=True)
            >>> _ = [io.write_video(
            ...     os.path.join("train_folder", label, f"video_{i + 1}.mp4"), data, 5, "libx264rgb", {"crf": "0"}
            ... ) for i, label in enumerate(["cat", "dog", "cat"])]
            >>> _ = [
            ...     io.write_video(
            ...         os.path.join("predict_folder", f"predict_video_{i}.mp4"), data, 5, "libx264rgb", {"crf": "0"}
            ...     ) for i in range(1, 4)
            ... ]

        .. doctest::

            >>> from flash import Trainer
            >>> from flash.video import VideoClassifier, VideoClassificationData
            >>> datamodule = VideoClassificationData.from_folders(
            ...     train_folder="train_folder",
            ...     predict_folder="predict_folder",
            ...     transform_kwargs=dict(image_size=(244, 244)),
            ...     batch_size=2,
            ... )
            >>> datamodule.num_classes
            2
            >>> datamodule.labels
            ['cat', 'dog']
            >>> model = VideoClassifier(backbone="x3d_xs", num_classes=datamodule.num_classes)
            >>> trainer = Trainer(fast_dev_run=True)
            >>> trainer.fit(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Training...
            >>> trainer.predict(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Predicting...

        .. testcleanup::

            >>> import shutil
            >>> shutil.rmtree("train_folder")
            >>> shutil.rmtree("predict_folder")
        """

        ds_kw = dict(
            data_pipeline_state=DataPipelineState(),
            transform_kwargs=transform_kwargs,
            input_transforms_registry=cls.input_transforms_registry,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )

        return cls(
            input_cls(RunningStage.TRAINING, train_folder, transform=train_transform, **ds_kw),
            input_cls(RunningStage.VALIDATING, val_folder, transform=val_transform, **ds_kw),
            input_cls(RunningStage.TESTING, test_folder, transform=test_transform, **ds_kw),
            predict_input_cls(RunningStage.PREDICTING, predict_folder, transform=predict_transform, **ds_kw),
            **data_module_kwargs,
        )

    @classmethod
    def from_data_frame(
        cls,
        input_field: str,
        target_fields: Optional[Union[str, Sequence[str]]] = None,
        train_data_frame: Optional[pd.DataFrame] = None,
        train_videos_root: Optional[str] = None,
        train_resolver: Optional[Callable[[str, str], str]] = None,
        val_data_frame: Optional[pd.DataFrame] = None,
        val_videos_root: Optional[str] = None,
        val_resolver: Optional[Callable[[str, str], str]] = None,
        test_data_frame: Optional[pd.DataFrame] = None,
        test_videos_root: Optional[str] = None,
        test_resolver: Optional[Callable[[str, str], str]] = None,
        predict_data_frame: Optional[pd.DataFrame] = None,
        predict_videos_root: Optional[str] = None,
        predict_resolver: Optional[Callable[[str, str], str]] = None,
        train_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        val_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        test_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        predict_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
        input_cls: Type[Input] = VideoClassificationDataFrameInput,
        predict_input_cls: Type[Input] = VideoClassificationDataFramePredictInput,
        transform_kwargs: Optional[Dict] = None,
        **data_module_kwargs: Any,
    ) -> "VideoClassificationData":
        """Load the :class:`~flash.video.classification.data.VideoClassificationData` from pandas DataFrame objects
        containing video file paths and their corresponding targets.

        Input video file paths will be extracted from the ``input_field`` in the DataFrame.
        The supported file extensions are: ``.mp4``, and ``.avi``.
        The targets will be extracted from the ``target_fields`` in the DataFrame and can be in any of our
        :ref:`supported classification target formats <formatting_classification_targets>`.
        To learn how to customize the transforms applied for each stage, read our
        :ref:`customizing transforms guide <customizing_transforms>`.

        Args:
            input_field: The field (column name) in the DataFrames containing the video file paths.
            target_fields: The field (column name) or list of fields in the DataFrames containing the targets.
            train_data_frame: The DataFrame to use when training.
            train_videos_root: The root directory containing train videos.
            train_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a video
                file path.
            val_data_frame: The DataFrame to use when validating.
            val_videos_root: The root directory containing validation videos.
            val_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a video
                file path.
            test_data_frame: The DataFrame to use when testing.
            test_videos_root: The root directory containing test videos.
            test_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a video
                file path.
            predict_data_frame: The DataFrame to use when predicting.
            predict_videos_root: The root directory containing predict videos.
            predict_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a
                video file path.
            train_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when training.
            val_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when validating.
            test_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when testing.
            predict_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when
                predicting.
            clip_sampler: The clip sampler to use. One of: ``"uniform"``, ``"random"``, ``"constant_clips_per_video"``.
            clip_duration: The duration of clips to sample.
            clip_sampler_kwargs: Additional keyword arguments to use when constructing the clip sampler.
            video_sampler: Sampler for the internal video container. This defines the order videos are decoded and,
                if necessary, the distributed split.
            decode_audio: If True, also decode audio from video.
            decoder: The decoder to use to decode videos. One of: ``"pyav"``, ``"torchvision"``. Not used for frame
                videos.
            input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the data.
            predict_input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the prediction data.
            transform_kwargs: Dict of keyword arguments to be provided when instantiating the transforms.
            data_module_kwargs: Additional keyword arguments to provide to the
                :class:`~flash.core.data.data_module.DataModule` constructor.

        Returns:
            The constructed :class:`~flash.video.classification.data.VideoClassificationData`.

        Examples
        ________

        .. testsetup::

            >>> import os
            >>> import torch
            >>> from torchvision import io
            >>> data = torch.randint(255, (10, 64, 64, 3))
            >>> os.makedirs("train_folder", exist_ok=True)
            >>> os.makedirs("predict_folder", exist_ok=True)
            >>> _ = [io.write_video(
            ...     os.path.join("train_folder", f"video_{i}.mp4"), data, 5, "libx264rgb", {"crf": "0"}
            ... ) for i in range(1, 4)]
            >>> _ = [
            ...     io.write_video(
            ...         os.path.join("predict_folder", f"predict_video_{i}.mp4"), data, 5, "libx264rgb", {"crf": "0"}
            ...     ) for i in range(1, 4)
            ... ]

        .. doctest::

            >>> from pandas import DataFrame
            >>> from flash import Trainer
            >>> from flash.video import VideoClassifier, VideoClassificationData
            >>> train_data_frame = DataFrame.from_dict(
            ...     {
            ...         "videos": ["video_1.mp4", "video_2.mp4", "video_3.mp4"],
            ...         "targets": ["cat", "dog", "cat"],
            ...     }
            ... )
            >>> predict_data_frame = DataFrame.from_dict(
            ...     {
            ...         "videos": ["predict_video_1.mp4", "predict_video_2.mp4", "predict_video_3.mp4"],
            ...     }
            ... )
            >>> datamodule = VideoClassificationData.from_data_frame(
            ...     "videos",
            ...     "targets",
            ...     train_data_frame=train_data_frame,
            ...     train_videos_root="train_folder",
            ...     predict_data_frame=predict_data_frame,
            ...     predict_videos_root="predict_folder",
            ...     transform_kwargs=dict(image_size=(244, 244)),
            ...     batch_size=2,
            ... )
            >>> datamodule.num_classes
            2
            >>> datamodule.labels
            ['cat', 'dog']
            >>> model = VideoClassifier(backbone="x3d_xs", num_classes=datamodule.num_classes)
            >>> trainer = Trainer(fast_dev_run=True)
            >>> trainer.fit(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Training...
            >>> trainer.predict(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Predicting...

        .. testcleanup::

            >>> import shutil
            >>> shutil.rmtree("train_folder")
            >>> shutil.rmtree("predict_folder")
        """

        ds_kw = dict(
            data_pipeline_state=DataPipelineState(),
            transform_kwargs=transform_kwargs,
            input_transforms_registry=cls.input_transforms_registry,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )

        train_data = (train_data_frame, input_field, target_fields, train_videos_root, train_resolver)
        val_data = (val_data_frame, input_field, target_fields, val_videos_root, val_resolver)
        test_data = (test_data_frame, input_field, target_fields, test_videos_root, test_resolver)
        predict_data = (predict_data_frame, input_field, predict_videos_root, predict_resolver)

        return cls(
            input_cls(RunningStage.TRAINING, *train_data, transform=train_transform, **ds_kw),
            input_cls(RunningStage.VALIDATING, *val_data, transform=val_transform, **ds_kw),
            input_cls(RunningStage.TESTING, *test_data, transform=test_transform, **ds_kw),
            predict_input_cls(RunningStage.PREDICTING, *predict_data, transform=predict_transform, **ds_kw),
            **data_module_kwargs,
        )

    @classmethod
    def from_csv(
        cls,
        input_field: str,
        target_fields: Optional[Union[str, List[str]]] = None,
        train_file: Optional[PATH_TYPE] = None,
        train_videos_root: Optional[PATH_TYPE] = None,
        train_resolver: Optional[Callable[[PATH_TYPE, Any], PATH_TYPE]] = None,
        val_file: Optional[PATH_TYPE] = None,
        val_videos_root: Optional[PATH_TYPE] = None,
        val_resolver: Optional[Callable[[PATH_TYPE, Any], PATH_TYPE]] = None,
        test_file: Optional[str] = None,
        test_videos_root: Optional[str] = None,
        test_resolver: Optional[Callable[[PATH_TYPE, Any], PATH_TYPE]] = None,
        predict_file: Optional[str] = None,
        predict_videos_root: Optional[str] = None,
        predict_resolver: Optional[Callable[[PATH_TYPE, Any], PATH_TYPE]] = None,
        train_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        val_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        test_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        predict_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
        input_cls: Type[Input] = VideoClassificationCSVInput,
        predict_input_cls: Type[Input] = VideoClassificationCSVPredictInput,
        transform_kwargs: Optional[Dict] = None,
        **data_module_kwargs: Any,
    ) -> "VideoClassificationData":
        """Load the :class:`~flash.video.classification.data.VideoClassificationData` from CSV files containing
        video file paths and their corresponding targets.

        Input video file paths will be extracted from the ``input_field`` column in the CSV files.
        The supported file extensions are: ``.mp4``, and ``.avi``.
        The targets will be extracted from the ``target_fields`` in the CSV files and can be in any of our
        :ref:`supported classification target formats <formatting_classification_targets>`.
        To learn how to customize the transforms applied for each stage, read our
        :ref:`customizing transforms guide <customizing_transforms>`.

        Args:
            input_field: The field (column name) in the CSV files containing the video file paths.
            target_fields: The field (column name) or list of fields in the CSV files containing the targets.
            train_file: The CSV file to use when training.
            train_videos_root: The root directory containing train videos.
            train_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a video
                file path.
            val_file: The CSV file to use when validating.
            val_videos_root: The root directory containing validation videos.
            val_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a video
                file path.
            test_file: The CSV file to use when testing.
            test_videos_root: The root directory containing test videos.
            test_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a video
                file path.
            predict_file: The CSV file to use when predicting.
            predict_videos_root: The root directory containing predict videos.
            predict_resolver: Optionally provide a function which converts an entry from the ``input_field`` into a
                video file path.
            train_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when training.
            val_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when validating.
            test_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when testing.
            predict_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` type to use when
                predicting.
            clip_sampler: The clip sampler to use. One of: ``"uniform"``, ``"random"``, ``"constant_clips_per_video"``.
            clip_duration: The duration of clips to sample.
            clip_sampler_kwargs: Additional keyword arguments to use when constructing the clip sampler.
            video_sampler: Sampler for the internal video container. This defines the order videos are decoded and,
                if necessary, the distributed split.
            decode_audio: If True, also decode audio from video.
            decoder: The decoder to use to decode videos. One of: ``"pyav"``, ``"torchvision"``. Not used for frame
                videos.
            input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the data.
            predict_input_cls: The :class:`~flash.core.data.io.input.Input` type to use for loading the prediction data.
            transform_kwargs: Dict of keyword arguments to be provided when instantiating the transforms.
            data_module_kwargs: Additional keyword arguments to provide to the
                :class:`~flash.core.data.data_module.DataModule` constructor.

        Returns:
            The constructed :class:`~flash.video.classification.data.VideoClassificationData`.

        Examples
        ________

        .. testsetup::

            >>> import os
            >>> import torch
            >>> from torchvision import io
            >>> from pandas import DataFrame
            >>> data = torch.randint(255, (10, 64, 64, 3))
            >>> os.makedirs("train_folder", exist_ok=True)
            >>> os.makedirs("predict_folder", exist_ok=True)
            >>> _ = [io.write_video(
            ...     os.path.join("train_folder", f"video_{i}.mp4"), data, 5, "libx264rgb", {"crf": "0"}
            ... ) for i in range(1, 4)]
            >>> _ = [
            ...     io.write_video(
            ...         os.path.join("predict_folder", f"predict_video_{i}.mp4"), data, 5, "libx264rgb", {"crf": "0"}
            ...     ) for i in range(1, 4)
            ... ]
            >>> DataFrame.from_dict({
            ...         "videos": ["video_1.mp4", "video_2.mp4", "video_3.mp4"],
            ...         "targets": ["cat", "dog", "cat"],
            ... }).to_csv("train_data.csv", index=False)
            >>> DataFrame.from_dict({
            ...         "videos": ["predict_video_1.mp4", "predict_video_2.mp4", "predict_video_3.mp4"],
            ... }).to_csv("predict_data.csv", index=False)

        The file ``train_data.csv`` contains the following:

        .. code-block::

            videos,targets
            video_1.mp4,cat
            video_2.mp4,dog
            video_3.mp4,cat

        The file ``predict_data.csv`` contains the following:

        .. code-block::

            videos
            predict_video_1.mp4
            predict_video_2.mp4
            predict_video_3.mp4

        .. doctest::

            >>> from flash import Trainer
            >>> from flash.video import VideoClassifier, VideoClassificationData
            >>> datamodule = VideoClassificationData.from_csv(
            ...     "videos",
            ...     "targets",
            ...     train_file="train_data.csv",
            ...     train_videos_root="train_folder",
            ...     predict_file="predict_data.csv",
            ...     predict_videos_root="predict_folder",
            ...     transform_kwargs=dict(image_size=(244, 244)),
            ...     batch_size=2,
            ... )
            >>> datamodule.num_classes
            2
            >>> datamodule.labels
            ['cat', 'dog']
            >>> model = VideoClassifier(backbone="x3d_xs", num_classes=datamodule.num_classes)
            >>> trainer = Trainer(fast_dev_run=True)
            >>> trainer.fit(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Training...
            >>> trainer.predict(model, datamodule=datamodule)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            Predicting...

        .. testcleanup::

            >>> import shutil
            >>> shutil.rmtree("train_folder")
            >>> shutil.rmtree("predict_folder")
            >>> os.remove("train_data.csv")
            >>> os.remove("predict_data.csv")
        """

        ds_kw = dict(
            data_pipeline_state=DataPipelineState(),
            transform_kwargs=transform_kwargs,
            input_transforms_registry=cls.input_transforms_registry,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )

        train_data = (train_file, input_field, target_fields, train_videos_root, train_resolver)
        val_data = (val_file, input_field, target_fields, val_videos_root, val_resolver)
        test_data = (test_file, input_field, target_fields, test_videos_root, test_resolver)
        predict_data = (predict_file, input_field, predict_videos_root, predict_resolver)

        return cls(
            input_cls(RunningStage.TRAINING, *train_data, transform=train_transform, **ds_kw),
            input_cls(RunningStage.VALIDATING, *val_data, transform=val_transform, **ds_kw),
            input_cls(RunningStage.TESTING, *test_data, transform=test_transform, **ds_kw),
            predict_input_cls(RunningStage.PREDICTING, *predict_data, transform=predict_transform, **ds_kw),
            **data_module_kwargs,
        )

    @classmethod
    @requires("fiftyone")
    def from_fiftyone(
        cls,
        train_dataset: Optional[SampleCollection] = None,
        val_dataset: Optional[SampleCollection] = None,
        test_dataset: Optional[SampleCollection] = None,
        predict_dataset: Optional[SampleCollection] = None,
        train_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        val_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        test_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        predict_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
        label_field: str = "ground_truth",
        input_cls: Type[Input] = VideoClassificationFiftyOneInput,
        transform_kwargs: Optional[Dict] = None,
        **data_module_kwargs,
    ) -> "VideoClassificationData":

        ds_kw = dict(
            data_pipeline_state=DataPipelineState(),
            transform_kwargs=transform_kwargs,
            input_transforms_registry=cls.input_transforms_registry,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
            label_field=label_field,
        )

        return cls(
            input_cls(RunningStage.TRAINING, train_dataset, transform=train_transform, **ds_kw),
            input_cls(RunningStage.VALIDATING, val_dataset, transform=val_transform, **ds_kw),
            input_cls(RunningStage.TESTING, test_dataset, transform=test_transform, **ds_kw),
            input_cls(RunningStage.PREDICTING, predict_dataset, transform=predict_transform, **ds_kw),
            **data_module_kwargs,
        )

    @classmethod
    def from_labelstudio(
        cls,
        export_json: str = None,
        train_export_json: str = None,
        val_export_json: str = None,
        test_export_json: str = None,
        predict_export_json: str = None,
        data_folder: str = None,
        train_data_folder: str = None,
        val_data_folder: str = None,
        test_data_folder: str = None,
        predict_data_folder: str = None,
        train_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        val_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        test_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        predict_transform: INPUT_TRANSFORM_TYPE = VideoClassificationInputTransform,
        val_split: Optional[float] = None,
        multi_label: Optional[bool] = False,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
        input_cls: Type[Input] = LabelStudioVideoClassificationInput,
        transform_kwargs: Optional[Dict] = None,
        **data_module_kwargs,
    ) -> "VideoClassificationData":
        """Creates a :class:`~flash.core.data.data_module.DataModule` object
        from the given export file and data directory using the
        :class:`~flash.core.data.io.input.Input` of name
        :attr:`~flash.core.data.io.input.InputFormat.FOLDERS`
        from the passed or constructed :class:`~flash.core.data.io.input_transform.InputTransform`.

        Args:
            export_json: path to label studio export file
            train_export_json: path to label studio export file for train set,
            overrides export_json if specified
            val_export_json: path to label studio export file for validation
            test_export_json: path to label studio export file for test
            predict_export_json: path to label studio export file for predict
            data_folder: path to label studio data folder
            train_data_folder: path to label studio data folder for train data set,
            overrides data_folder if specified
            val_data_folder: path to label studio data folder for validation data
            test_data_folder: path to label studio data folder for test data
            predict_data_folder: path to label studio data folder for predict data
            train_transform: The dictionary of transforms to use during training which maps
                :class:`~flash.core.data.io.input_transform.InputTransform` hook names to callable transforms.
            val_transform: The dictionary of transforms to use during validation which maps
                :class:`~flash.core.data.io.input_transform.InputTransform` hook names to callable transforms.
            test_transform: The dictionary of transforms to use during testing which maps
                :class:`~flash.core.data.io.input_transform.InputTransform` hook names to callable transforms.
            predict_transform: The dictionary of transforms to use during predicting which maps
                :class:`~flash.core.data.io.input_transform.InputTransform` hook names to callable transforms.
            data_fetcher: The :class:`~flash.core.data.callback.BaseDataFetcher` to pass to the
                :class:`~flash.core.data.data_module.DataModule`.
            input_transform: The :class:`~flash.core.data.io.input_transform.InputTransform` to pass to the
                :class:`~flash.core.data.data_module.DataModule`. If ``None``, ``cls.input_transform_cls``
                will be constructed and used.
            val_split: The ``val_split`` argument to pass to the :class:`~flash.core.data.data_module.DataModule`.
            multi_label: Whether the label are multi encoded.
            clip_sampler: Defines how clips should be sampled from each video.
            clip_duration: Defines how long the sampled clips should be for each video.
            clip_sampler_kwargs: Additional keyword arguments to use when constructing the clip sampler.
            video_sampler: Sampler for the internal video container. This defines the order videos are decoded and,
                    if necessary, the distributed split.
            decode_audio: If True, also decode audio from video.
            decoder: Defines what type of decoder used to decode a video.
            data_module_kwargs: Additional keyword arguments to use when constructing the datamodule.

        Returns:
            The constructed data module.

        Examples::

            data_module = DataModule.from_labelstudio(
                export_json='project.json',
                data_folder='label-studio/media/upload',
                val_split=0.8,
            )
        """

        train_data, val_data, test_data, predict_data = _parse_labelstudio_arguments(
            export_json=export_json,
            train_export_json=train_export_json,
            val_export_json=val_export_json,
            test_export_json=test_export_json,
            predict_export_json=predict_export_json,
            data_folder=data_folder,
            train_data_folder=train_data_folder,
            val_data_folder=val_data_folder,
            test_data_folder=test_data_folder,
            predict_data_folder=predict_data_folder,
            val_split=val_split,
            multi_label=multi_label,
        )

        ds_kw = dict(
            data_pipeline_state=DataPipelineState(),
            transform_kwargs=transform_kwargs,
            input_transforms_registry=cls.input_transforms_registry,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )

        return cls(
            input_cls(RunningStage.TRAINING, train_data, transform=train_transform, **ds_kw),
            input_cls(RunningStage.VALIDATING, val_data, transform=val_transform, **ds_kw),
            input_cls(RunningStage.TESTING, test_data, transform=test_transform, **ds_kw),
            input_cls(RunningStage.PREDICTING, predict_data, transform=predict_transform, **ds_kw),
            **data_module_kwargs,
        )
