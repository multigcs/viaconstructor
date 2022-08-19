class DrawReaderBase:
    can_save_tabs = False

    def get_segments(self) -> list[dict]:
        return []

    def get_minmax(self) -> list[float]:
        return []

    def get_size(self) -> list[float]:
        return []

    def draw(self, draw_function, user_data=()) -> None:
        pass

    def draw_3d(self):
        pass

    def save_tabs(self, tabs: list) -> None:
        pass

    def save_starts(self, objects: dict) -> None:
        pass

    @staticmethod
    def suffix() -> list[str]:
        return []
