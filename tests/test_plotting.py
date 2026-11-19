import unittest
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.plotting import draw_figure
from spaceship_viewer.presentation import Presentation
from spaceship_viewer.state import ViewState


class PlottingTests(unittest.TestCase):
    def test_labels_do_not_overlap_or_clip_and_objects_are_retained(self):
        for comparison in (False, True):
            fig = Figure(figsize=(12.8, 9.), dpi=100)
            FigureCanvasAgg(fig)
            panels = draw_figure(fig, built_in_catalog(), ViewState(beta=np.sqrt(3)/2),
                                 Presentation(comparison=comparison, max_labels=16, selected_row=0), 'Orion')
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            for panel in panels:
                ax = panel['ax']
                self.assertEqual(len(panel['rows']), panel['scene'].n_visible)
                boxes = [text.get_window_extent(renderer) for text in panel['labels']]
                for i, box in enumerate(boxes):
                    self.assertTrue(ax.bbox.contains(box.x0, box.y0) and ax.bbox.contains(box.x1, box.y1))
                    self.assertFalse(any(box.overlaps(other) for other in boxes[:i]))

    def test_presentation_does_not_change_direction_or_doppler(self):
        fig = Figure(figsize=(10., 8.), dpi=100)
        FigureCanvasAgg(fig)
        state = ViewState(beta=.87)
        first = draw_figure(fig, built_in_catalog(), state, Presentation(), 'Orion')[0]['scene']
        second = draw_figure(fig, built_in_catalog(), state, Presentation(grid=False, marker_scale=.4, max_labels=0), 'Orion')[0]['scene']
        for field in ('doppler', 'apparent', 'visible', 'x_deg', 'y_deg'):
            np.testing.assert_array_equal(getattr(first, field), getattr(second, field))

    def test_square_export_captions_fit_page(self):
        fig = Figure(figsize=(8., 8.), dpi=100)
        FigureCanvasAgg(fig)
        draw_figure(fig, built_in_catalog(), ViewState(beta=np.sqrt(3)/2), Presentation(),
                    'Orion · inherited bright-star demo', for_export=True)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for text in fig.texts:
            box = text.get_window_extent(renderer)
            self.assertTrue(fig.bbox.contains(box.x0, box.y0) and fig.bbox.contains(box.x1, box.y1), text.get_text())


if __name__ == '__main__':
    unittest.main()
