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
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Type, Union

import pandas as pd
import torch
from pytorch_lightning.utilities.exceptions import MisconfigurationException
from torch.utils.data import Sampler

from flash.core.data.io.classification_input import ClassificationInputMixin, ClassificationState
from flash.core.data.io.input import DataKeys, Input, IterableInput
from flash.core.data.utilities.classification import MultiBinaryTargetFormatter
from flash.core.data.utilities.data_frame import read_csv, resolve_files, resolve_targets
from flash.core.data.utilities.paths import list_valid_files, make_dataset, PATH_TYPE
from flash.core.integrations.fiftyone.utils import FiftyOneLabelUtilities
from flash.core.utilities.imports import _FIFTYONE_AVAILABLE, _PYTORCHVIDEO_AVAILABLE, lazy_import

if _FIFTYONE_AVAILABLE:
    fol = lazy_import("fiftyone.core.labels")
    SampleCollection = "fiftyone.core.collections.SampleCollection"
else:
    fol = None
    SampleCollection = None

if _PYTORCHVIDEO_AVAILABLE:
    from pytorchvideo.data.clip_sampling import ClipSampler, make_clip_sampler
    from pytorchvideo.data.encoded_video import EncodedVideo
    from pytorchvideo.data.labeled_video_dataset import LabeledVideoDataset
    from pytorchvideo.data.labeled_video_paths import LabeledVideoPaths
else:
    ClipSampler, LabeledVideoDataset, EncodedVideo, ApplyTransformToKey = None, None, None, None


def _make_clip_sampler(
    clip_sampler: Union[str, "ClipSampler"] = "random",
    clip_duration: float = 2,
    clip_sampler_kwargs: Dict[str, Any] = None,
) -> "ClipSampler":
    if clip_sampler_kwargs is None:
        clip_sampler_kwargs = {}
    return make_clip_sampler(clip_sampler, clip_duration, **clip_sampler_kwargs)


class VideoClassificationInput(IterableInput, ClassificationInputMixin):
    def load_data(
        self,
        files: List[PATH_TYPE],
        targets: List[Any],
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
    ) -> "LabeledVideoDataset":
        dataset = LabeledVideoDataset(
            LabeledVideoPaths(list(zip(files, targets))),
            _make_clip_sampler(clip_sampler, clip_duration, clip_sampler_kwargs),
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )
        if not self.predicting:
            self.load_target_metadata([sample[1] for sample in dataset._labeled_videos._paths_and_labels])
        return dataset

    def load_sample(self, sample):
        sample["label"] = self.format_target(sample["label"])
        return sample


class VideoClassificationFoldersInput(VideoClassificationInput):
    def load_data(
        self,
        path: str,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
    ) -> "LabeledVideoDataset":
        return super().load_data(
            *make_dataset(path, extensions=("mp4", "avi")),
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )


class VideoClassificationFilesInput(VideoClassificationInput):
    def load_data(
        self,
        paths: List[str],
        targets: List[Any],
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
    ) -> "LabeledVideoDataset":
        return super().load_data(
            paths,
            targets,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )


class VideoClassificationDataFrameInput(VideoClassificationInput):
    def load_data(
        self,
        data_frame: pd.DataFrame,
        input_key: str,
        target_keys: Union[str, List[str]],
        root: Optional[PATH_TYPE] = None,
        resolver: Optional[Callable[[Optional[PATH_TYPE], Any], PATH_TYPE]] = None,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
    ) -> "LabeledVideoDataset":
        result = super().load_data(
            resolve_files(data_frame, input_key, root, resolver),
            resolve_targets(data_frame, target_keys),
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )

        # If we had binary multi-class targets then we also know the labels (column names)
        if (
            self.training
            and isinstance(self.target_formatter, MultiBinaryTargetFormatter)
            and isinstance(target_keys, List)
        ):
            classification_state = self.get_state(ClassificationState)
            self.set_state(ClassificationState(target_keys, classification_state.num_classes))

        return result


class VideoClassificationCSVInput(VideoClassificationDataFrameInput):
    def load_data(
        self,
        csv_file: PATH_TYPE,
        input_key: str,
        target_keys: Optional[Union[str, List[str]]] = None,
        root: Optional[PATH_TYPE] = None,
        resolver: Optional[Callable[[Optional[PATH_TYPE], Any], PATH_TYPE]] = None,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
    ) -> "LabeledVideoDataset":
        data_frame = read_csv(csv_file)
        if root is None:
            root = os.path.dirname(csv_file)
        return super().load_data(
            data_frame,
            input_key,
            target_keys,
            root,
            resolver,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )


class VideoClassificationFiftyOneInput(VideoClassificationInput):
    def load_data(
        self,
        sample_collection: SampleCollection,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
        label_field: str = "ground_truth",
    ) -> "LabeledVideoDataset":
        label_utilities = FiftyOneLabelUtilities(label_field, fol.Classification)
        label_utilities.validate(sample_collection)

        return super().load_data(
            sample_collection.values("filepath"),
            sample_collection.values(label_field + ".label"),
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )


class VideoClassificationPathsPredictInput(Input):
    def predict_load_data(
        self,
        paths: List[str],
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        decode_audio: bool = False,
        decoder: str = "pyav",
        **_: Any,
    ) -> Iterable[Tuple[str, Any]]:
        paths = list_valid_files(paths, valid_extensions=("mp4", "avi"))
        self._clip_sampler = _make_clip_sampler(clip_sampler, clip_duration, clip_sampler_kwargs)
        self._decode_audio = decode_audio
        self._decoder = decoder
        return paths

    def predict_load_sample(self, sample: str) -> Dict[str, Any]:
        video = EncodedVideo.from_path(sample, decode_audio=self._decode_audio, decoder=self._decoder)
        (
            clip_start,
            clip_end,
            clip_index,
            aug_index,
            is_last_clip,
        ) = self._clip_sampler(0.0, video.duration, None)

        loaded_clip = video.get_clip(clip_start, clip_end)

        clip_is_null = (
            loaded_clip is None or loaded_clip["video"] is None or (loaded_clip["audio"] is None and self._decode_audio)
        )

        if clip_is_null:
            raise MisconfigurationException(
                f"The provided video is too short {video.duration} to be clipped at {self._clip_sampler._clip_duration}"
            )

        frames = loaded_clip["video"]
        audio_samples = loaded_clip["audio"]
        return {
            "video": frames,
            "video_name": video.name,
            "video_index": 0,
            "clip_index": clip_index,
            "aug_index": aug_index,
            **({"audio": audio_samples} if audio_samples is not None else {}),
            DataKeys.METADATA: {"filepath": sample},
        }


class VideoClassificationDataFramePredictInput(VideoClassificationPathsPredictInput):
    def predict_load_data(
        self,
        data_frame: pd.DataFrame,
        input_key: str,
        root: Optional[PATH_TYPE] = None,
        resolver: Optional[Callable[[Optional[PATH_TYPE], Any], PATH_TYPE]] = None,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
    ) -> Iterable[Tuple[str, Any]]:
        return super().predict_load_data(
            resolve_files(data_frame, input_key, root, resolver),
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )


class VideoClassificationCSVPredictInput(VideoClassificationDataFramePredictInput):
    def predict_load_data(
        self,
        csv_file: PATH_TYPE,
        input_key: str,
        root: Optional[PATH_TYPE] = None,
        resolver: Optional[Callable[[Optional[PATH_TYPE], Any], PATH_TYPE]] = None,
        clip_sampler: Union[str, "ClipSampler"] = "random",
        clip_duration: float = 2,
        clip_sampler_kwargs: Dict[str, Any] = None,
        video_sampler: Type[Sampler] = torch.utils.data.RandomSampler,
        decode_audio: bool = False,
        decoder: str = "pyav",
    ) -> Iterable[Tuple[str, Any]]:
        data_frame = read_csv(csv_file)
        if root is None:
            root = os.path.dirname(csv_file)
        return super().predict_load_data(
            data_frame,
            input_key,
            root,
            resolver,
            clip_sampler=clip_sampler,
            clip_duration=clip_duration,
            clip_sampler_kwargs=clip_sampler_kwargs,
            video_sampler=video_sampler,
            decode_audio=decode_audio,
            decoder=decoder,
        )
