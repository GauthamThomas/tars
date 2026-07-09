"""Rich terminal UI for TARS - live scrolling transcription stream."""

import time
from collections import deque

from rich.console import RenderableType, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align


class TARSDisplay:
    """Live terminal display for TARS transcription and reactions."""

    def __init__(self):
        self.transcript_lines: deque[tuple[str, str | None, str | None]] = deque(maxlen=30)
        # Each entry: (text, trigger_name, color)
        self.partial_line = ""
        self.reaction = None  # (text, color, expiry_time)
        self.triggers_fired = 0
        self.status = "listening"  # listening / processing / fired
        self._paused = False

    def add_sentence(self, text: str, trigger_name: str = None, color: str = None):
        """Add completed sentence. If trigger_name provided, highlight it."""
        self.transcript_lines.append((text, trigger_name, color))

    def set_partial(self, text: str):
        """Update the partial (in-progress) transcription."""
        self.partial_line = text

    def show_reaction(self, reaction_text: str, color: str):
        """Show reaction panel. Auto-dismisses after 4 seconds."""
        self.reaction = (reaction_text, color, time.time() + 4.0)

    def _build_header(self) -> Panel:
        """Build the header panel with status indicator."""
        status_symbols = {
            "listening": "●",
            "processing": "◐",
            "fired": "◆",
        }
        status_colors = {
            "listening": "green",
            "processing": "yellow",
            "fired": "red",
        }

        symbol = status_symbols.get(self.status, "●")
        color = status_colors.get(self.status, "green")

        status_text = Text.assemble(
            (" TARS ", "bold white on blue"),
            (" ", ""),
            (symbol, f"bold {color}"),
            ("  ", ""),
            (f"listening", f"dim {color}"),
        )

        if self._paused:
            status_text.append("  ⏸  PAUSED", "bold yellow")

        counter_text = Text(f"triggers fired: {self.triggers_fired}", "dim white")
        counter_text.justify = "right"

        header = Table.grid(expand=True)
        header.add_column(ratio=1)
        header.add_column(ratio=1, justify="right")
        header.add_row(status_text, counter_text)

        return Panel(header, style="black", border_style="bright_blue", padding=(0, 1))

    def _build_transcript(self) -> Panel:
        """Build the transcript stream panel."""
        renderables = []

        for text, trigger_name, color in self.transcript_lines:
            if trigger_name and color:
                t = Text(text, style=f"bold {color}")
            else:
                t = Text(text, style="dim white")
            renderables.append(t)

        # Add partial line at the bottom if present
        if self.partial_line:
            partial = Text(self.partial_line, style="dim grey50 italic")
            renderables.append(partial)

        if not renderables:
            renderables.append(Text("Waiting for speech...", style="dim grey50 italic"))

        content = Group(*renderables)

        return Panel(
            content,
            title="Transcript",
            border_style="bright_blue",
            padding=(1, 2),
        )

    def _build_reaction(self) -> Panel | None:
        """Build the reaction panel if active."""
        if self.reaction is None:
            return None

        text, color, expiry = self.reaction
        if time.time() > expiry:
            self.reaction = None
            return None

        # Build reaction display
        content = Text.assemble(
            ("  🔊  ", "bold white"),
            (f'"{text}"', f"bold {color}"),
        )

        panel = Panel(
            Align.center(content),
            style=f"on {color}",
            border_style=color,
            padding=(1, 2),
        )
        return panel

    def _build_footer(self) -> Panel:
        """Build the footer with keyboard shortcuts."""
        shortcuts = Text.assemble(
            ("[P] ", "bold bright_blue"),
            ("pause  ", "dim white"),
            ("[Q] ", "bold bright_blue"),
            ("quit  ", "dim white"),
            ("[R] ", "bold bright_blue"),
            ("reload triggers", "dim white"),
        )
        return Panel(
            Align.center(shortcuts),
            style="black",
            border_style="bright_blue",
            padding=(0, 1),
        )

    def render(self) -> RenderableType:
        """Return the full renderable for rich.live."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="transcript", ratio=1),
            Layout(name="reaction", size=5),
            Layout(name="footer", size=3),
        )

        layout["header"].update(self._build_header())
        layout["transcript"].update(self._build_transcript())

        reaction_panel = self._build_reaction()
        if reaction_panel:
            layout["reaction"].update(reaction_panel)
        else:
            layout["reaction"].update(Panel("", border_style="black", padding=(1, 2)))

        layout["footer"].update(self._build_footer())

        return layout

    def toggle_pause(self):
        """Toggle pause state."""
        self._paused = not self._paused
        return self._paused