# ------------------------------------------------------------------------------
#
# Project: pytdml
# Authors: Boyi Shangguan, Kaixuan Wang, Zhaoyan Wu
# Created: 2022-05-04
# Modified: 2023-10-27
# Email: sgby@whu.edu.cn
#
# ------------------------------------------------------------------------------
#
# Copyright (c) 2022 OGC Training Data Markup Language for AI Standard Working Group
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ------------------------------------------------------------------------------
import json
from typing import Union, Any

from pytdml.type import TrainingDataset, EOTrainingDataset


def _is_empty(obj):
    if isinstance(obj, (str, list, dict)):
        return len(obj) == 0
    elif obj is None:
        return True
    else:
        return False


def remove_empty_values(d):
    if isinstance(d, dict):
        return {
            k: v
            for k, v in ((k, remove_empty_values(v)) for k, v in d.items())
            if not _is_empty(v)
        }
    elif isinstance(d, list):
        return [v for v in (remove_empty_values(v) for v in d) if not _is_empty(v)]
    elif isinstance(d, tuple):
        return tuple(v for v in (remove_empty_values(v) for v in d) if not _is_empty(v))
    else:
        return d


def write_to_json(
    td: TrainingDataset or EOTrainingDataset,
    file_path: str,
    indent: Union[int, str] = 4,
):
    """
    Writes a TrainingDataset to a JSON file.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            remove_empty_values(td.to_dict()), f, indent=indent, ensure_ascii=False
        )
        # json.dump(remove_empty(td.dict()), f, indent=indent, ensure_ascii=False)
