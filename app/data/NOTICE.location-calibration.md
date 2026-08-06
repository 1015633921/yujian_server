# 出生地点校准坐标数据说明

`china_city_centers_v1.json` 是当前小程序省/市选择器的离线、版本化坐标表。

- 覆盖范围：仅覆盖 `miniprogram/pages/assessment/assessment.js` 中的省/市（含自治州、地区、林区和当前列出的县级选项）选择器。
- 坐标系统：WGS84。
- 精度：`city-seat`，即所选城市或行政区的城市席位近似坐标；它不是用户的精确出生地址，也不应用于更细的区县级断言。
- 时区：按领土记录 IANA 时区（中国大陆 `Asia/Shanghai`、台湾 `Asia/Taipei`、香港 `Asia/Hong_Kong`、澳门 `Asia/Macau`）。
- 运行方式：服务运行时只读取本地 JSON；不会把出生地点实时提交给地图或地理编码服务。

## 来源与署名

主体数据来自 [GeoNames country dumps](https://download.geonames.org/export/dump/)，采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；具体下载 URL、压缩包 SHA-256 和解压文件 SHA-256 均写在 JSON 的 `source_manifest` 中。

GeoNames 下载快照中没有以下五个当前选择器中的新疆新设市：铁门关市、双河市、可克达拉市、新星市、白杨市。它们在 JSON 中以 `coordinate_origin: "manual-wikidata-override"` 明确标识，使用对应 [Wikidata](https://www.wikidata.org/) 条目的 P625 坐标声明（CC0），并保留记录 ID 和原始链接。

## 再生成与校验

先下载 GeoNames 的 `CN.zip`、`TW.zip`、`HK.zip`、`MO.zip` 并解压为同目录的 `.txt` 文件，然后在仓库根目录执行：

```bash
python3 scripts/build_location_dataset.py \
  --source-dir /path/to/geonames-source \
  --output app/data/china_city_centers_v1.json
```

提交前使用以下命令验证源文件、当前选择器和生成结果仍完全一致：

```bash
python3 scripts/build_location_dataset.py \
  --source-dir /path/to/geonames-source \
  --output app/data/china_city_centers_v1.json \
  --check
```

若某个选择器项缺失、最佳来源候选仍有歧义、代码重复、坐标不合法或时区不一致，生成器会以非零状态退出；不会写入局部数据集。

若来源快照、手动覆盖或选择器坐标发生实质变更，必须同时递增生成器中的 `DATASET_VERSION`，让历史报告继续保留其生成时使用的数据版本；`records_sha256` 用于审查该版本内的内容完整性。
