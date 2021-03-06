from models import Model, ModelState, AnalyticSegment

import utils
import utils.meta
import numpy as np
import pandas as pd
import scipy.signal
from scipy.fftpack import fft
from typing import Optional, List, Tuple
import math
from scipy.signal import argrelextrema
from scipy.stats import gaussian_kde
from analytic_types import AnalyticUnitId, TimeSeries
from analytic_types.learning_info import LearningInfo


@utils.meta.JSONClass
class JumpModelState(ModelState):
    def __init__(
        self,
        confidence: float = 0,
        jump_height: float = 0,
        jump_length: float = 0,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.confidence = confidence
        self.jump_height = jump_height
        self.jump_length = jump_length


class JumpModel(Model):
    
    def get_model_type(self) -> (str, bool):
        model = 'jump'
        type_model = True
        return (model, type_model)
    
    def find_segment_center(self, dataframe: pd.DataFrame, start: int, end: int) -> int:
        data = dataframe['value']
        segment = data[start: end]
        segment_center_index = utils.find_pattern_center(segment, start, 'jump')
        return segment_center_index

    def get_state(self, cache: Optional[dict] = None) -> JumpModelState:
        return JumpModelState.from_json(cache)

    def do_fit(
        self,
        dataframe: pd.DataFrame,
        labeled_segments: List[AnalyticSegment],
        deleted_segments: List[AnalyticSegment],
        learning_info: LearningInfo
    ) -> None:
        data = utils.cut_dataframe(dataframe)
        data = data['value']
        window_size = self.state.window_size
        last_pattern_center = self.state.pattern_center
        self.state.pattern_center = list(set(last_pattern_center + learning_info.segment_center_list))
        self.state.pattern_model = utils.get_av_model(learning_info.patterns_list)
        convolve_list = utils.get_convolve(self.state.pattern_center, self.state.pattern_model, data, window_size)
        correlation_list = utils.get_correlation(self.state.pattern_center, self.state.pattern_model, data, window_size)
        height_list = learning_info.patterns_value

        del_conv_list = []
        delete_pattern_timestamp = []
        for segment in deleted_segments:
            segment_cent_index = segment.center_index
            delete_pattern_timestamp.append(segment.pattern_timestamp)
            deleted_jump = utils.get_interval(data, segment_cent_index, window_size)
            deleted_jump = utils.subtract_min_without_nan(deleted_jump)
            del_conv_jump = scipy.signal.fftconvolve(deleted_jump, self.state.pattern_model)
            if len(del_conv_jump): del_conv_list.append(max(del_conv_jump))

        self._update_fiting_result(self.state, learning_info.confidence, convolve_list, del_conv_list)
        self.state.jump_height = float(min(learning_info.pattern_height, default = 1))
        self.state.jump_length = int(max(learning_info.pattern_width, default = 1))

    def do_detect(self, dataframe: pd.DataFrame) -> TimeSeries:
        data = utils.cut_dataframe(dataframe)
        data = data['value']
        possible_jumps = utils.find_jump(data, self.state.jump_height, self.state.jump_length + 1)
        result = self.__filter_detection(possible_jumps, data)
        return [(val - 1, val + 1) for val in result]

    def __filter_detection(self, segments: List[int], data: pd.Series):
        delete_list = []
        variance_error = self.state.window_size
        close_patterns = utils.close_filtering(segments, variance_error)
        segments = utils.best_pattern(close_patterns, data, 'max')

        if len(segments) == 0 or len(self.state.pattern_center) == 0:
            segments = []
            return segments
        pattern_data = self.state.pattern_model
        upper_bound = self.state.convolve_max * 1.2
        lower_bound = self.state.convolve_min * 0.8
        delete_up_bound = self.state.conv_del_max * 1.02
        delete_low_bound = self.state.conv_del_min * 0.98
        for segment in segments:
            if segment > self.state.window_size and segment < (len(data) - self.state.window_size):
                convol_data = utils.get_interval(data, segment, self.state.window_size)
                percent_of_nans = convol_data.isnull().sum() / len(convol_data)
                if len(convol_data) == 0 or percent_of_nans > 0.5:
                    delete_list.append(segment)
                    continue
                elif 0 < percent_of_nans <= 0.5:
                    nan_list = utils.find_nan_indexes(convol_data)
                    convol_data = utils.nan_to_zero(convol_data, nan_list)
                    pattern_data = utils.nan_to_zero(pattern_data, nan_list)
                conv = scipy.signal.fftconvolve(convol_data, pattern_data)
                try:
                    if max(conv) > upper_bound or max(conv) < lower_bound:
                        delete_list.append(segment)
                    elif max(conv) < delete_up_bound and max(conv) > delete_low_bound:
                        delete_list.append(segment)
                except ValueError:
                    delete_list.append(segment)
            else:
                delete_list.append(segment)
        for item in delete_list:
            segments.remove(item)

        return set(segments)
