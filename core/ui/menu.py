from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box


class MenuManager:
    def __init__(self):
        self.console = Console()
    
    def display_welcome(self):
        """Отображает приветственный экран с логотипом."""
        self.console.clear()
        
        combined_text = Text()
        combined_text.append("\n📢 Channel: ", style="bold white")
        combined_text.append("https://t.me/D3_vin", style="cyan")
        combined_text.append("\n💬 Chat: ", style="bold white")
        combined_text.append("https://t.me/D3vin_chat", style="cyan")
        combined_text.append("\n📁 GitHub: ", style="bold white")
        combined_text.append("https://github.com/D3-vin", style="cyan")
        combined_text.append("\n📁 Version: ", style="bold white")
        combined_text.append("5.5.1", style="green")
        combined_text.append("\n")

        info_panel = Panel(
            Align.left(combined_text),
            title="[bold blue]Grass Auto Farm mod 5.5.1[/bold blue]",
            subtitle="[bold magenta]Dev by D3vin[/bold magenta]",
            box=box.ROUNDED,
            border_style="bright_blue",
            padding=(0, 1),
            width=50
        )

        self.console.print(info_panel)
        self.console.print()
    
    def show_menu(self):
        """Отображает главное меню выбора режима."""
        menu_text = Text()
        menu_text.append("Choose mode:", style="bold cyan")
        menu_text.append("\n1) Farm 1.25x", style="light_green")
        menu_text.append("\n2) Farm 1x", style="light_green")
        menu_text.append("\n3) Claim rewards", style="light_yellow")
        menu_text.append("\n4) Login only (update tokens)", style="light_blue")
        menu_text.append("\n5) Exit", style="light_red")

        menu_panel = Panel(
            Align.left(menu_text),
            title="[bold green]GRASS Bot Menu[/bold green]",
            box=box.ROUNDED,
            border_style="bright_green",
            padding=(1, 2),
            width=50
        )

        self.console.print(menu_panel)
        
        while True:
            try:
                choice = int(self.console.input("\n[bold cyan]Enter the number (1-5): [/bold cyan]"))
                if 1 <= choice <= 5:
                    return choice
                else:
                    self.console.print("[bold red]Error: enter a number from 1 to 5[/bold red]")
            except ValueError:
                self.console.print("[bold red]Error: enter a number from 1 to 5[/bold red]")
    
    def show_mode_selected(self, mode_name: str):
        """Отображает выбранный режим."""
        self.console.print(f"\n[bold green]Selected mode: {mode_name}[/bold green]")
    
    def show_exit_message(self):
        """Отображает сообщение о выходе."""
        self.console.print("[bold red]Exiting program[/bold red]")
