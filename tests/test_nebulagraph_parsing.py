from app.database.nebulagraph import NebulaGraphDatabase


class FakeValue:
    def __init__(self, value):
        self.value = value

    def is_null(self):
        return self.value is None

    def is_bool(self):
        return isinstance(self.value, bool)

    def is_int(self):
        return isinstance(self.value, int) and not isinstance(self.value, bool)

    def is_float(self):
        return isinstance(self.value, float)

    def is_string(self):
        return isinstance(self.value, str)

    def is_list(self):
        return isinstance(self.value, list)

    def is_map(self):
        return isinstance(self.value, dict)

    def as_bool(self):
        return self.value

    def as_int(self):
        return self.value

    def as_double(self):
        return self.value

    def as_string(self):
        return self.value

    def get_list(self):
        return [FakeValue(item) for item in self.value]

    def get_map(self):
        return {key: FakeValue(value) for key, value in self.value.items()}


class FakeRow:
    def __init__(self, values):
        self.values = values


class FakeData:
    column_names = ["source_id", "target_id"]

    def rows(self):
        return [FakeRow([FakeValue("char-1"), FakeValue("char-2")])]


class FakeResult:
    data = FakeData()

    def row_size(self):
        return 1

    def row_values(self, index):
        return self.data.rows()[index].values


def test_value_to_python_handles_nested_values():
    db = NebulaGraphDatabase()

    assert db._value_to_python(FakeValue({"name": "林砚", "scores": [1, 2]})) == {"name": "林砚", "scores": [1, 2]}


def test_result_rows_uses_column_names():
    db = NebulaGraphDatabase()

    assert db._result_rows(FakeResult()) == [{"source_id": "char-1", "target_id": "char-2"}]
