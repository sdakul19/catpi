from kivy.uix.button import Button
from kivy.graphics import Ellipse, Color


class CircularButton(Button):

    image_size = NumericProperty(30.0)
    label_spacing = NumericProperty(5.0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (100, 100)  # Ensure square shape

        with self.canvas.before:
            self.bg_color = Color(0.2, 0.6, 0.9, 1)  # Light blue
            self.bg_ellipse = Ellipse(pos=self.pos, size=self.size)

        self.bind(pos=self.update_shape, size=self.update_shape)

    def update_shape(self, *args):
        self.bg_ellipse.pos = self.pos
        self.bg_ellipse.size = self.size

