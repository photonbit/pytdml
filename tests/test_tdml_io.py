import json
import requests
import jsonschema

from pytdml.io.coco_converter import convert_coco_to_tdml
from pytdml.io.stac_converter import convert_stac_to_tdml
from pytdml.io.tdml_readers import read_from_json
from pytdml.io.yaml_converter import yaml_to_eo_tdml

base_url = "https://raw.githubusercontent.com/opengeospatial/TrainingDML-AI_SWG/main/schemas/1.0/json_schema/{}.json"
remote_schema_url = base_url.format("ai_eoTrainingDataset")
response = requests.get(remote_schema_url)
remote_schema = response.json()


def test_read_and_write():
    tdml_path = r"tests/data/json/WHU-building.json"
    td = read_from_json(tdml_path)
    with open(tdml_path, "r") as f:
        data = json.load(f)
    assert td.to_dict() == data


def test_ai_scene_label_data():
    tdml_path = r"tests/data/json/AiRound-aerial.json"
    td = read_from_json(tdml_path)
    with open(tdml_path, "r") as f:
        data = json.load(f)
    assert td.to_dict() == data


def test_ai_object_label_data():
    tdml_path = r"tests/data/object-detection/COWC_partial.json"
    td = read_from_json(tdml_path)
    with open(tdml_path, "r") as f:
        data = json.load(f)
    print("td.to_dict():", td.to_dict())
    print("data:", data)
    assert td.to_dict() == data


def test_yaml_to_eo_tdml():
    yaml_path = r"tests/data/yaml/UiT_HCD_California_2017.yml"
    tdml_path = r"tests/data/json/UiT_HCD_California_2017.json"
    td = yaml_to_eo_tdml(yaml_path)
    with open(tdml_path, "r") as f:
        data = json.load(f)
    assert td.to_dict() == data


def test_convert_stac_to_tdml():
    stac_file_path = r"tests/data/stac/collection.json"
    td = convert_stac_to_tdml(stac_file_path)
    jsonschema.validate(instance=td.to_dict(), schema=remote_schema)


def test_coco_converter_Panoptic_Segmentation():
    coco_file_path = r"tests/data/coco/panoptic_val2017.json"
    td_dict = convert_coco_to_tdml(coco_file_path).to_dict()
    td_dict["data"] = td_dict["data"][:2]
    jsonschema.validate(instance=td_dict, schema=remote_schema)


def test_coco_converter_Image_Captioning():
    coco_file_path = r"tests/data/coco/captions_val2014.json"
    td_dict = convert_coco_to_tdml(coco_file_path).to_dict()
    td_dict["data"] = td_dict["data"][:2]
    jsonschema.validate(instance=td_dict, schema=remote_schema)
