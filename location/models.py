from django.conf import settings
from django.db import models


DEFAULT_MAP_TILE_URL = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
DEFAULT_MAP_TILE_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> '
    'contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>'
)


class LocationSetting(models.Model):
    """Configuration for map tile providers and GPS tracking thresholds."""

    name = models.CharField(max_length=60, unique=True, default="default")
    tile_layer_url = models.CharField(
        max_length=255,
        default=DEFAULT_MAP_TILE_URL,
        help_text="Leaflet tile URL template for the base map.",
    )
    tile_layer_attribution = models.CharField(
        max_length=255,
        default=DEFAULT_MAP_TILE_ATTRIBUTION,
        help_text="Attribution HTML required by the tile provider.",
    )
    default_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=17.6868,
        help_text="Default fallback latitude when user GPS is not available.",
    )
    default_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=83.2185,
        help_text="Default fallback longitude when user GPS is not available.",
    )
    min_update_interval_seconds = models.PositiveIntegerField(
        default=5,
        help_text="Minimum seconds between delivery partner location database writes.",
    )
    min_movement_meters = models.PositiveIntegerField(
        default=10,
        help_text="Minimum meters moved before writing a new location history point.",
    )
    partner_location_max_age_seconds = models.PositiveIntegerField(
        default=120,
        help_text="Maximum age of a delivery partner GPS fix for assignment and tracking.",
    )
    delivery_assignment_accept_timeout_seconds = models.PositiveIntegerField(
        default=90,
        help_text="Seconds a partner has to accept a delivery offer before reassignment.",
    )
    delivery_assignment_max_attempts = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of partner offers before assignment is marked failed.",
    )
    delivery_assignment_initial_radius_km = models.PositiveIntegerField(
        default=3,
        help_text="Initial partner search radius; it expands by this value per attempt.",
    )
    delivery_assignment_max_radius_km = models.PositiveIntegerField(
        default=15,
        help_text="Maximum distance to search for an eligible delivery partner.",
    )
    routing_enabled = models.BooleanField(
        default=False,
        help_text="Enable external road routing API (fallback to straight visual line when false).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "location"
        verbose_name = "Location setting"
        verbose_name_plural = "Location settings"

    def __str__(self):
        return f"Location Settings ({self.name})"

    def save(self, *args, **kwargs):
        self.name = "default"
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        setting, _ = cls.objects.get_or_create(name="default")
        current_default_url = getattr(settings, "MAP_TILE_URL", DEFAULT_MAP_TILE_URL)
        current_default_attr = getattr(settings, "MAP_TILE_ATTRIBUTION", DEFAULT_MAP_TILE_ATTRIBUTION)
        if "tile.openstreetmap.org" in (setting.tile_layer_url or ""):
            setting.tile_layer_url = current_default_url
            setting.tile_layer_attribution = current_default_attr
            setting.save(update_fields=["tile_layer_url", "tile_layer_attribution"])
        return setting
