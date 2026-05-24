"""
The Conqueror — entry point.
State → Logic → Display (display never mutates state).
"""

import sys
import time

from display.console import ConsoleDisplay
from game_factory import create_game
from logic.player import PlayerController, execute_command
from logic.simulation import Simulation

COUNTRY_MENU = """
Pick your country (number) or press Enter to observe AI-only:
  1 United States   2 China          3 Russia         4 India
  5 United Kingdom  6 France         7 Germany        8 Japan
  9 South Korea    10 Israel        11 Pakistan       12 Iran
 13 Saudi Arabia   14 Turkey        15 Brazil        16 North Korea
 17 Australia      18 Ukraine       19 South Africa  20 Indonesia
 21 Argentina
"""

TICK_INTERVAL = 0.25


def pick_player(controller: PlayerController) -> None:
    names = [c.name for c in controller.state.countries]
    print(COUNTRY_MENU)
    choice = input("> ").strip()
    if not choice:
        return
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(names):
            result = controller.assign_country(names[idx])
            print(result.message)
    except ValueError:
        print("Invalid choice — spectator mode (no player actions).")


def render_screen(display: ConsoleDisplay, player: PlayerController) -> None:
    print("\033[2J\033[H", end="")
    print(display.render_full())
    if player.country:
        print(f"\n{display.render_relationships(player.country.name)}")


def process_command(
    cmd: str,
    player: PlayerController,
    display: ConsoleDisplay,
    simulation: Simulation,
) -> bool:
    """Handle one command. Returns False if the game should exit."""
    outcome = execute_command(player, cmd)
    if outcome is None:
        print("(unknown command — try h for help)")
        return True
    if outcome == "quit":
        print("Quitting.")
        return False
    if isinstance(outcome, str):
        if outcome == "quit":
            return False
        if outcome == "pause":
            simulation.manual_pause = True
            simulation.clock.pause()
            print("Clock paused. Type 'r' to resume.")
        elif outcome == "resume":
            if simulation.needs_player_response:
                print("Respond to the attack first (clock stays paused).")
            else:
                simulation.manual_pause = False
                simulation.clock.resume()
                print("Clock resumed.")
        else:
            if not handle_meta(outcome, display):
                return False
        return True

    print(outcome.message)
    if outcome.success and simulation.needs_player_response is False:
        if not simulation.manual_pause:
            simulation.clock.resume()
    return True


def handle_meta(meta: str, display: ConsoleDisplay) -> bool:
    if meta == "quit":
        return False
    if meta == "targets":
        print(display.render_targets())
    elif meta == "help":
        print(display.render_help())
    elif meta == "info":
        print(display.render_player_panel() or "(no player)")
    print()
    return True


def wait_for_player_input(
    player: PlayerController,
    display: ConsoleDisplay,
    simulation: Simulation,
    *,
    prompt: str,
) -> bool:
    """Blocking input while the clock is paused. Returns False to quit."""
    render_screen(display, player)
    print(prompt)
    if hint := player.suggested_reactive_command():
        print(f"  Suggested: {hint}")
    print(display.render_targets())
    print()

    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nQuitting.")
            return False
        if not cmd:
            continue
        if not process_command(cmd, player, display, simulation):
            return False

        if simulation.needs_player_response:
            print("\nStill waiting for your response...")
            continue
        if simulation.manual_pause:
            continue
        return True


def run_game_loop(simulation: Simulation, display: ConsoleDisplay, player: PlayerController) -> None:
    print(display.render_help())
    print("The clock PAUSES automatically when you must react or when you press 'p'.\n")

    running = True
    while running and not simulation.state.winner:
        if simulation.needs_player_response:
            simulation.clock.pause()
            provoker, provocation = simulation.player_pending_reaction
            running = wait_for_player_input(
                player,
                display,
                simulation,
                prompt=(
                    f"\n*** CLOCK PAUSED — {provoker} {provocation}ed you ***\n"
                    f"Enter a command (e.g. s <#> or a <#>), or 't' for targets:"
                ),
            )
            continue

        if simulation.manual_pause or simulation.clock.paused:
            running = wait_for_player_input(
                player,
                display,
                simulation,
                prompt="\n*** CLOCK PAUSED (you pressed p) — type 'r' to resume ***",
            )
            continue

        simulation.tick(TICK_INTERVAL)
        render_screen(display, player)
        print("\n[p]=pause  [t]=targets  [h]=help  [q]=quit", flush=True)
        time.sleep(TICK_INTERVAL)

    if simulation.state.winner:
        render_screen(display, player)
        print(f"\nGame over — {simulation.state.winner} wins!")
    elif simulation.state.player_country:
        simulation.save_score(won=False)
        print("Score saved.")


def main() -> None:
    simulation, player = create_game()
    display = ConsoleDisplay(simulation.state, simulation)

    print(f"Loaded {len(simulation.state.countries)} countries.")
    print("Tip: run  python app.py  for the web UI.\n")
    pick_player(player)

    if simulation.state.player_country:
        print(display.render_player_panel())
        print()

    run_game_loop(simulation, display, player)


if __name__ == "__main__":
    main()
