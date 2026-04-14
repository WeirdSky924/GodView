---
id: base_json_output
name: JSON输出格式规范
description: 规范Agent输出JSON格式的结构和要求
category: output
tags:
  - output
  - json
  - format
use_cases:
  - 规范化输出格式
  - JSON解析保证
priority: 100
is_system: true
---

# JSON输出格式规范

请以 JSON 格式返回你的响应。

## 要求

- 使用标准的 JSON 格式，不要包含任何额外的说明文字
- JSON 对象的键使用双引号
- 值可以是字符串、数字、布尔值、数组或嵌套对象
- 如果需要返回多个项目，使用数组格式
- 确保 JSON 语法正确，可以被解析

## 示例格式

```json
{
  "status": "success",
  "data": {
    "key": "value"
  },
  "errors": []
}
```
