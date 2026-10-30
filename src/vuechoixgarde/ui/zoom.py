from dataclasses import dataclass


@dataclass
class ZoomState:
    scale: float = 1.0
    offset: tuple[float, float] = (0.0, 0.0)

    MIN_SCALE = 1.0
    MAX_SCALE = 8.0

    def zoom_at(self, anchor: tuple[float, float], factor: float) -> None:
        new_scale = min(self.MAX_SCALE, max(self.MIN_SCALE, self.scale * factor))
        scale_ratio = new_scale / self.scale
        self.offset = (
            anchor[0] - (anchor[0] - self.offset[0]) * scale_ratio,
            anchor[1] - (anchor[1] - self.offset[1]) * scale_ratio,
        )
        self.scale = new_scale

    def clamp_offset(
        self,
        image_size: tuple[float, float],
        viewport_size: tuple[float, float],
    ) -> None:
        self.offset = tuple(
            self._clamp_axis(offset, image_extent * self.scale, viewport_extent)
            for offset, image_extent, viewport_extent in zip(
                self.offset, image_size, viewport_size, strict=True
            )
        )  # type: ignore[assignment]

    def reset(self) -> None:
        self.scale = self.MIN_SCALE
        self.offset = (0.0, 0.0)

    @staticmethod
    def _clamp_axis(offset: float, image_extent: float, viewport_extent: float) -> float:
        if image_extent < viewport_extent:
            return (viewport_extent - image_extent) / 2
        return min(0.0, max(viewport_extent - image_extent, offset))
