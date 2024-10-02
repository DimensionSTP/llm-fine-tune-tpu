from typing import Any, Dict

import torch

from transformers import AutoTokenizer

from datasets import load_dataset


class StructuralDataLoader:
    def __init__(
        self,
        data_path: str,
        split_ratio: float,
        seed: int,
        instruction_column_name: str,
        data_column_name: str,
        target_column_name: str,
        max_length: int,
        model_path: str,
        padding_side: str,
    ) -> None:
        self.data_path = data_path
        self.split_ratio = split_ratio
        self.seed = seed
        self.instruction_column_name = instruction_column_name
        self.data_column_name = data_column_name
        self.target_column_name = target_column_name
        self.max_length = max_length
        self.data_encoder = AutoTokenizer.from_pretrained(
            model_path,
            use_fast=True,
        )
        if self.data_encoder.pad_token_id is None:
            self.data_encoder.pad_token_id = self.data_encoder.eos_token_id
        self.data_encoder.padding_side = padding_side

    def __call__(self):
        dataset = load_dataset(
            "parquet",
            data_files={
                "train": f"{self.data_path}/train.parquet",
            },
        )["train"]
        train_test_split = dataset.train_test_split(
            test_size=self.split_ratio,
            seed=self.seed,
            shuffle=True,
        )
        train_dataset = train_test_split["train"]
        eval_dataset = train_test_split["test"]

        tokenized_train_dataset = train_dataset.map(
            lambda datas: self.preprocess_function(
                datas,
            ),
            batched=True,
        )
        tokenized_train_dataset = tokenized_train_dataset.map(self.add_labels)
        tokenized_eval_dataset = eval_dataset.map(
            lambda datas: self.preprocess_function(
                datas,
            ),
            batched=True,
        )
        tokenized_eval_dataset = tokenized_eval_dataset.map(self.add_labels)
        return {
            "train": tokenized_train_dataset,
            "eval": tokenized_eval_dataset,
        }

    def generate_prompt(
        self,
        instruction: str,
        input: str,
        response: str,
    ) -> str:
        prompt = f"""### Instruction:
{instruction}

### Input:
{input}

### Response:
{response}""".strip()
        return prompt

    def preprocess_function(
        self,
        datas: Any,
    ) -> Dict[str, torch.Tensor]:
        prompts = [
            self.generate_prompt(
                instruction,
                input,
                response,
            )
            for instruction, input, response in zip(
                datas[self.instruction_column_name],
                datas[self.data_column_name],
                datas[self.target_column_name],
            )
        ]
        return self.data_encoder(
            prompts,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
            add_special_tokens=True,
        )

    def add_labels(
        self,
        datas: Dict[str, list],
    ) -> Dict[str, list]:
        datas["labels"] = datas["input_ids"].copy()
        return datas
