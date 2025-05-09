# ------------------------------------------------------------------------------
#
# Project: pytdml
# Authors: Shuaiqi Liu
# Created: 2023-02-04
# Email: sqi_liu@whu.edu.cn
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
import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import geojson
from minio.error import MinioException
from tqdm import tqdm

from datalibrary.s3Client import minio_client as client
from pytdml.ml.tdml_image_crop import CropWithImage, CropWithTargetImage
from pytdml.type.extended_types import AI_EOTrainingData, AI_ObjectLabel, AI_PixelLabel
from pytdml.ml.utils import split_data_url, generate_local_file_path, image_open

# Creating a Mutual Exclusion Lock
lock = multiprocessing.Lock()


class Task:
    scene_classification = "Scene Classification"
    object_detection = "Object Detection"
    semantic_segmentation = "Semantic Segmentation"
    change_detection = "Change Detection"
    model_3d_reconstruction = "3D Model Reconstruction"


def download_file(bucket_name, object_name, file_name):
    """
    Downloads a file from a MinIO bucket and saves it to the local file system.

    Args:
        bucket_name (str): The name of the MinIO bucket containing the file to download.
        object_name (str): The name of the object (file) to download from the bucket.
        file_name (str): The name of the file to save the downloaded object to on the local file system.

    Returns:
        bool: True if the file was successfully downloaded and saved to the local file system,
              False otherwise.

    Raises:
        MinioException: If an error occurs during the download process.
    """
    try:
        client.fget_object(bucket_name, object_name, file_name)
    except MinioException as e:
        print(f"Failed to download {object_name}: {e}")
        return False
    return True


def download_scene_data(args):
    """
    Downloads training data and saves it to a local directory,
    Args:
        args (tuple): A tuple containing a training data object and the directory where the data should be downloaded to.
    Returns:
        A data item object with the updated data_url field.
    """

    data_item, download_dir, _ = args
    assert data_item.data_url is not None, "data_url cannot be None"
    sample_url = data_item.data_url[0]

    bucket_name, object_name = split_data_url(sample_url)
    file_path = generate_local_file_path(download_dir, sample_url)
    with lock:
        if os.path.exists(file_path):
            data_item.data_url = [file_path]
            return data_item
        if not os.path.exists(os.path.dirname(file_path)):
            try:
                os.makedirs(os.path.dirname(file_path))
            except OSError as error:
                print(error)
                return

        if not download_file(bucket_name, object_name, file_path):
            return
        data_item.data_url = [file_path]
        return data_item


def download_object_data(args):
    dataset_name, data_item, download_dir, crop = args
    sample_url = data_item.data_url[0]
    labels = data_item.labels

    bucket_name, image_object_name = split_data_url(sample_url)
    file_path = generate_local_file_path(download_dir, sample_url)

    # Check and create directory
    if not os.path.exists(os.path.dirname(file_path)):

        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
        except OSError as error:
            print(error)
            return []  # If directory creation fails, skip the current item
    if crop is None:
        # Check if the file already exists to avoid duplicate downloads
        if not os.path.exists(file_path):
            # The function should catch possible exceptions to prevent process crashes
            try:
                download_file(bucket_name, image_object_name, file_path)
                data_item.data_url = [file_path]
            except Exception as error:
                print(f"Failed to download {image_object_name}: {error}")
                return []  # Download failed, return an empty list
        else:
            print(f"File already exists: {file_path}")
            # Even for already downloaded files, the data_item URL should be updated
            data_item.data_url = [file_path]

        return [data_item]
    else:
        new_td_list = []
        data_stream = client.get_object(bucket_name, image_object_name)
        img = image_open(data_stream)

        crop_object = CropWithTargetImage(*crop)  # Supplement parameters
        download_dir = os.path.join(
            download_dir, "EOTrainingDataset", dataset_name, "image"
        )
        crop_coords, targets = crop_object(
            img, labels, download_dir, sample_url.split("/")[-1]
        )
        index = 0
        for i, crop_image_url in enumerate(crop_coords):

            labels = []

            for target in targets[i]:
                # json_object = {"bbox": target["object"], "type": "Feature"}
                labels.append(
                    AI_ObjectLabel(
                        object=geojson.loads(json.dumps(target["object"])),
                        label_class=target["class"],
                        bbox_type=target["bboxType"],
                        is_negative=target["isNegative"],
                    )
                )

            new_d = AI_EOTrainingData(
                id=str(data_item.id + "_crop_" + str(index)),
                # extent=data_item.extent,
                number_of_labels=len(targets[i]),
                training_type=data_item.training_type,
                data_url=[crop_image_url],
                labels=labels,
            )
            index = index + 1
            new_td_list.append(new_d)
    return new_td_list


def download_segmentation_data(args):
    dataset_name, data_item, download_dir, crop = args
    sample_url = data_item.data_url[0]
    label_url = data_item.labels[0].image_url

    # download training data
    bucket_name, image_object_name = split_data_url(sample_url)
    label_object_name = label_url.replace(bucket_name, "")

    image_path = generate_local_file_path(download_dir, sample_url)
    label_path = generate_local_file_path(download_dir, label_url)
    with lock:
        try:
            image_dir = os.path.dirname(image_path)
            if not os.path.exists(image_dir):
                os.makedirs(image_dir)

            label_dir = os.path.dirname(label_path)
            if not os.path.exists(label_dir):
                os.makedirs(label_dir)

        except OSError as error:
            print(error)

    if crop is None:
        # download imagery data
        download_file(bucket_name, image_object_name, image_path)
        # download label data
        download_file(bucket_name, label_object_name, label_path)
        data_item.data_url = [image_path]
        data_item.labels[0].image_url = label_path
        return [data_item]
    else:
        new_td_list = []
        img_stream = client.get_object(bucket_name, image_object_name)
        label_stream = client.get_object(bucket_name, label_object_name)
        img = image_open(img_stream)
        label = image_open(label_stream)

        crop_image = CropWithImage(*crop)
        crop_imgs = crop_image(img, image_dir, sample_url.split("/")[-1])
        crop_labels = crop_image(label, label_dir, label_url.split("/")[-1])

        index = 0
        for crop_image_url, crop_label_url in zip(crop_imgs, crop_labels):
            new_d = AI_EOTrainingData(
                id=str(data_item.id + "_crop_" + str(index)),
                labels=[AI_PixelLabel(image_url=crop_label_url)],
                data_url=[crop_image_url],
            )
            index = index + 1
            new_td_list.append(new_d)

        return new_td_list


def download_changeDetection_data(args):
    dataset_name, data_item, download_dir, lock, crop = args
    sample_url = data_item.data_url
    label_url = data_item.labels[0].image_url
    bucket_name, bef_image_object_name = split_data_url(sample_url[0])
    bukcet_name, af_image_object_name = split_data_url(sample_url[1])
    bucket_name, label_object_name = split_data_url(label_url)

    bef_image_path = generate_local_file_path(download_dir, sample_url[0])
    af_image_path = generate_local_file_path(download_dir, sample_url[1])
    label_path = generate_local_file_path(download_dir, label_url)
    bef_image_dir = os.path.dirname(bef_image_path)
    af_image_dir = os.path.dirname(af_image_path)
    label_dir = os.path.dirname(label_path)
    with lock:
        try:
            if not os.path.exists(bef_image_dir):
                os.makedirs(bef_image_dir)
            if not os.path.exists(af_image_dir):
                os.makedirs(af_image_dir)
            if not os.path.exists(label_dir):
                os.makedirs(label_dir)
        except OSError as error:
            print(error)
    bf_img_name = sample_url[0].split("/")[-1]
    af_img_name = sample_url[1].split("/")[-1]
    label_path = os.path.join(label_dir, label_url.split("/")[-1])
    if crop is None:

        download_file(bucket_name, bef_image_object_name, bef_image_path)
        download_file(bucket_name, af_image_object_name, af_image_path)

        download_file(bucket_name, label_object_name, label_path)
        data_item.data_url = [bef_image_path, af_image_path]
        data_item.labels[0].image_url = label_path
        return [data_item]
    else:

        new_td_list = []
        bef_img_stream = client.get_object(bucket_name, bef_image_object_name)
        # Crop to the specified parameter
        bef_img = image_open(bef_img_stream)
        assert crop[0] < bef_img.shape[0] and crop[0] < bef_img.shape[1]
        crop_image = CropWithImage(*crop)  # crop parameters
        crop_bef_imgs = crop_image(bef_img, bef_image_dir, bf_img_name)

        af_img_stream = client.get_object(bucket_name, af_image_object_name)
        af_img = image_open(af_img_stream)
        crop_af_imgs = crop_image(af_img, af_image_dir, af_img_name)

        label_stream = client.get_object(bucket_name, label_object_name)
        label = image_open(label_stream)
        crop_labels = crop_image(label, label_dir, label_url.split("/")[-1])

        index = 0
        for crop_bef_image_url, crop_af_image_url, crop_label_url in zip(
            crop_bef_imgs, crop_af_imgs, crop_labels
        ):
            new_d = AI_EOTrainingData(
                id=str(data_item.id + "_crop_" + str(index)),
                labels=[AI_PixelLabel(image_url=crop_label_url)],
                data_url=[crop_bef_image_url, crop_af_image_url],
            )
            index = index + 1
            new_td_list.append(new_d)
        return new_td_list


def download_3MR_data(args):
    data_item, download_dir, lock = args
    sample_urls = data_item.data_url
    label_urls = data_item.labels[0].image_url

    def download_data(urls):
        data_url = []
        for url in urls:
            bucket_name, object_name = split_data_url(url)
            file_path = generate_local_file_path(url)
            if os.path.exists(file_path):
                data_url.append(file_path)
            if not os.path.exists(os.path.dirname(file_path)):
                with lock:
                    if not os.path.exists(os.path.dirname(file_path)):
                        try:
                            os.makedirs(os.path.dirname(file_path))
                        except OSError as error:
                            print(error)
                            return
                data_url.append(file_path)
                if not download_file(bucket_name, object_name, file_path):
                    return
        return data_url

    image_urls = download_data(sample_urls)
    label_urls = download_data(label_urls)

    data_item.data_url = image_urls
    data_item.labels[0].image_url = label_urls
    return data_item


def download_remote_object(root, url):
    bucket_name, object_name = split_data_url(url)
    file_path = generate_local_file_path(root, url)

    if not os.path.exists(os.path.dirname(file_path)):

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    download_file(bucket_name, object_name, file_path)
    img = image_open(file_path)
    return img, file_path


def DatasetDownload(taskType, data_list, download_dir, num_processes=8):
    """Multi-process download of datasets"""

    with multiprocessing.Manager() as manager:
        lock = manager.Lock()
        result_list = manager.list()
        with multiprocessing.Pool(processes=num_processes) as pool:

            args = [(data_item, download_dir, lock) for data_item in data_list.data]
            if taskType == Task.scene_classification:
                for result in tqdm(
                    pool.imap_unordered(download_scene_data, args), total=len(args)
                ):
                    result_list.append(result)
            if taskType == Task.model_3d_reconstruction:
                for result in tqdm(
                    pool.imap_unordered(download_3MR_data, args), total=len(args)
                ):
                    result_list.append(result)
        return list(result_list)


def DatasetDownload2(task_type, dataset, download_dir, crop, num_threads=8):
    result_list = []

    # Prepare args parameters
    args = [(dataset.name, data_item, download_dir, crop) for data_item in dataset.data]

    # Use ThreadPoolExecutor for thread pool management
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Assign download function based on task type
        if task_type == Task.object_detection:
            download_function = download_object_data
        elif task_type == Task.semantic_segmentation:
            download_function = download_segmentation_data
        elif task_type == Task.change_detection:
            download_function = download_changeDetection_data
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

        # Submit tasks to the thread pool
        futures = {executor.submit(download_function, arg): arg for arg in args}

        # Use tqdm to display progress bar
        for future in tqdm(as_completed(futures), total=len(futures)):
            try:
                result = future.result()
                result_list.extend(result)
            except Exception as exc:
                print(f"Generated an exception: {exc}")

    return result_list
