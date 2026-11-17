# Third-party sources

TGLib by Lutz Oettershagen is obtained under its MIT license. `build.cmd` fetches revision `e56c3ddb2b665455fb16aacca1044b99a62850f0` from [tgpublic/tglib](https://gitlab.com/tgpublic/tglib) into the ignored `vendor/tglib` directory. All 60 required source and license files must match the published [SHA-256 manifest](dependencies/tglib-source-sha256.json), which records the Windows checkout bytes. Upstream source, comments, copyright notices and license remain locally; they are not uploaded as this project's code. The [MIT license](licenses/TGLib-MIT.txt) is retained here. The library is described by Oettershagen and Mutzel, *TGLib: An Open-Source Library for Temporal Graph Analysis*, ICDM Workshops 2022, [DOI](https://doi.org/10.1109/ICDMW58026.2022.00160).

The study downloads public data from their original providers; those datasets are not relicensed by this repository. Users must follow the providers' terms and attribution requirements:

- [SNAP temporal data](https://snap.stanford.edu/data/): Bitcoin OTC, CollegeMsg, email-Eu-core-temporal, MathOverflow, Ask Ubuntu and Higgs. Per-file URLs and SHA-256 values are in `reference/inputs`.
- [Temporal Graph Benchmark export](https://huggingface.co/datasets/stanford-star/tgb): Coin, Comment and Flight, pinned to `af2aaea1b75bf58dcc9d01521d0347c89afec878`. The input manifest preserves each original URL and content hash.
- [Public transport connections](https://doi.org/10.5281/zenodo.1186215): Kuopio, Berlin, Paris, Sydney, Winnipeg, Detroit and Bordeaux. The published archive MD5 values are checked before extracting daily connections. See [the dataset publication](https://doi.org/10.1038/sdata.2018.89).

Python dependencies retain their upstream licenses. The tiny contact/query fixtures are included for functional testing; full input logs are obtained from the providers. Algorithm provenance and distinctions between author code and local implementations are recorded in [docs/baselines.md](docs/baselines.md).
