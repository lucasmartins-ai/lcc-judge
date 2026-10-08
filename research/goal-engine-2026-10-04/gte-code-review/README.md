---
license: apache-2.0
---

**English** | [中文](./README_zh.md)

[Arxiv PDF](https://arxiv.org/pdf/2407.19669), [HF paper page](https://huggingface.co/papers/2407.19669)

## Code implementation of new GTE encoders

This model is a BERT-like encoder with the following optimizations implemented:

1. Replacing absolute position embeddings with RoPE [^1].
2. Substituting the conventional activation functions with Gated Linear Units (GLU) [^2].
3. Setting attention dropout to 0 to use `xformers` and `flash_attn`.
4. Using unpadding to eliminate the needless computations for padding tokens [^3]. (this is off by default and should be used in conjunction with `xformers` for optimal acceleration).

### Recommendation: Enable Unpadding and Acceleration with `xformers`

This code supports the acceleration of attention computations using `xformers`, which can automatically choose the optimal implementation based on the type of device, such as `flash_attn`. Therefore, we can also achieve significant acceleration on old devices like the V100.


Firstly, install `xformers` (with `pytorch` pre-installed):
```
if pytorch is installed using conda:
    conda install xformers -c xformers
elif pytorch is installed using pip:
    # cuda 11.8 version
    pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu118
    # cuda 12.1 version
    pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu121
```
For more information, refer to [Installing xformers](https://github.com/facebookresearch/xformers?tab=readme-ov-file#installing-xformers).

Then, when loading the model, set `unpad_inputs` and `use_memory_efficient_attention` to `true`,
and set `torch_dtype` to `torch.float16` (or `torch.bfloat16`) to achieve the acceleration.

```python
import torch
from transformers import AutoModel, AutoTokenizer

path = 'Alibaba-NLP/gte-base-en-v1.5'
device = torch.device('cuda')
tokenzier = AutoTokenizer.from_pretrained(path)
model = AutoModel.from_pretrained(
    path,
    trust_remote_code=True,
    unpad_inputs=True,
    use_memory_efficient_attention=True,
    torch_dtype=torch.float16
).to(device)

inputs = tokenzier(['test input'], truncation=True, max_length=8192, padding=True, return_tensors='pt')

with torch.inference_mode():
    outputs = model(**inputs.to(device))

```

Alternatively, you can directly modify the `unpad_inputs` and `use_memory_efficient_attention` settings to `true` in the model's `config.json`,
eliminating the need to set them in the code.


---

<details>
  <summary> Clarification of Relationship with nomic-embed and nomicBERT </summary>

One may question the originality of our work and consider it a mere replication of `nomicBERT`. To clarify, our work is parallel but stems from the same idea as `nomicBERT`.

Applying RoPE and GLU to BERT to support longer texts is a straightforward idea. Our exploration of the transformer++ encoder (i.e., BERT + RoPE + GLU) began in August 2023.
And by November 2023, we had completed the `gte-base-en-v1.1`. Then, I went on to prepare for the ACL submission of the other project...

The release of `nomic-embed` [^4] brought to our attention the pressure, as well as provided us with more resources, which allowed us to continue with this project.
Without the outstanding work of `nomicai`, the release of `gte-v1.5` could have been delayed much longer. Thanks!

</details>

---

## Citation
```
@misc{zhang2024mgte,
  title={mGTE: Generalized Long-Context Text Representation and Reranking Models for Multilingual Text Retrieval}, 
  author={Xin Zhang and Yanzhao Zhang and Dingkun Long and Wen Xie and Ziqi Dai and Jialong Tang and Huan Lin and Baosong Yang and Pengjun Xie and Fei Huang and Meishan Zhang and Wenjie Li and Min Zhang},
  year={2024},
  eprint={2407.19669},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2407.19669}, 
}
```


[^1]: Su, Jianlin, Murtadha Ahmed, Yu Lu, Shengfeng Pan, Wen Bo, and Yunfeng Liu. "Roformer: Enhanced transformer with rotary position embedding." Neurocomputing 568 (2024): 127063.

[^2]: Shazeer, Noam. "Glu variants improve transformer." arXiv preprint arXiv:2002.05202 (2020).

[^3]: Portes, Jacob, Alexander Trott, Sam Havens, Daniel King, Abhinav Venigalla, Moin Nadeem, Nikhil Sardana, Daya Khudia, and Jonathan Frankle. "MosaicBERT: A Bidirectional Encoder Optimized for Fast Pretraining." Advances in Neural Information Processing Systems 36 (2024).

[^4]: Nussbaum, Zach, John X. Morris, Brandon Duderstadt, and Andriy Mulyar. "Nomic Embed: Training a Reproducible Long Context Text Embedder." arXiv preprint arXiv:2402.01613 (2024).