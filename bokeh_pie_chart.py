import math
from typing import Union, Dict

from bokeh.plotting import figure


class PieChart:
    MIN_VALUE = 0.001
    COLORS = ["yellow", "red", "lightblue", "green", "orange", "pink", "purple", "brown", "black", "grey"]

    def __init__(
            self,
            data: Dict[str, Union[int, float]],
            title: str,
            radius: float = 1,
            **kwargs):
        self._figure = figure(
            title=title,
            **kwargs
        )
        self._figure.xgrid.visible = False
        self._figure.ygrid.visible = False
        self._figure.toolbar.logo = None
        self._figure.xaxis.visible = False
        self._figure.yaxis.visible = False
        self._figure.title.text_color = "black"
        self._figure.title.align = "center"
        self._radius = radius
        self.line_color = "white"
        self.data = data
        self.show()

    def show(self):
        start_angle = [math.radians(0)]
        prev = start_angle[0]
        for i in self._radians[:-1]:
            start_angle.append(i + prev)
            prev += i
        end_angle = start_angle[1:] + [math.radians(0)]
        x = 0
        y = 0

        self._figure.renderers = []
        self._figure.legend.clear()
        for i in range(len(self._sectors)):
            if self._radians[i] == math.tau:
                self._figure.ellipse(
                    x=x,
                    y=y,
                    width=self._radius * 2,
                    height=self._radius * 2,
                    fill_color=self.COLORS[i],
                    legend_label=self._sectors[i],
                    line_color=self.line_color,
                )
                continue
            self._figure.wedge(
                x=x,
                y=y,
                radius=self._radius,
                start_angle=start_angle[i],
                end_angle=end_angle[i],
                color=self.COLORS[i],
                legend_label=self._sectors[i]
            )


    @property
    def figure(self) -> figure:
        return self._figure

    @property
    def data(self) -> Dict[str, Union[int, float]]:
        return self._data

    @data.setter
    def data(self, data: Dict[str, Union[int, float]]):
        self._data = data
        self._sectors = []
        self._radians = []
        total = sum(data.values())
        for key, value in data.items():
            if value < self.MIN_VALUE:
                continue
            self._sectors.append(key)
            self._radians.append(math.radians(value * 360 / total) if value < total else math.tau)
        self.show()
