import chess
from dotenv import load_dotenv
import anthropic
import os

load_dotenv()
api_key = os.getenv("API_KEY")
selected_model = os.getenv("MODEL")

client = anthropic.Anthropic()

def menu_loop():
  menu_dict = {
    "entry": "------------Welcome to Terminal Chess!------------",
    "barrier": "***********************************************",
    "op_1": "1. Find an opponent online.",
    "op_2": "2. Play locally against a LLM."
  }

  for entry in menu_dict.values():
    print(entry)
  
  user_selection = input()
  while user_selection not in ['1', '2']:
    user_selection = input("Please select a valid option!")
    print(menu_dict['op_1'])
    print(menu_dict['op_2'])

  if user_selection == '1':
    game_result = run_game()
  elif user_selection == '2':
    game_result = run_LLM_game()

  play_again_input = input("Thank you for playing! Would you like to play again? (Y/N)")
  if play_again_input.lower() == 'y' menu_loop() else exit(0)
  
# Finds a game online using simple matchmaking

def run_game():
  return 0


def gen_llm_move(board_state, side):
  prompt = f"You are playing a chess game on side: {side}"
  prompt += f"The last move is {board_state.peek()}"
  prompt += f"The current state of the board is:\n{board_state}"

  try:
    model_resp = client.messages.create(
      model = selected_model,
      max_tokens = 10,
      messages = [
        {'role': 'user', 'content': prompt}
      ]
    )

    resp_dict = model_resp.model_dump() if hasattr(model_resp, 'model_dump') else model_resp.__dict__
    if resp_dict.get('type') == 'error':
      print(f"Error: {resp_dict.get('error', {}).get('message')}")

  return ""


# Runs a game vs. a selected LLM locally

def run_LLM_game():


  player_side = input("Pick the side you want to play.")

  while player_side.lower() not in ['black', 'white']:
    player_side = input("Valid choices are: black, white")

  ai_side = 'black' if player_side == 'white' else 'white'
  ai_turn = True if player_side == 'black' else False

  is_game_ongoing = True
  game_board = chess.Board()
  move_count = 0

  while(is_game_ongoing):
    if ai_turn:
      current_move = gen_llm_move(game_board, ai_side)
      game_board.push_san(current_move)
      ai_turn = False
      move_count++
      print(game_board)
    else:
      move_input = input("Enter a move in valid chess algebraic notation.")
      invalid_move = True

      while(invalid_move):
        print(game_board)
        print(f"Last move: {game_board.peek()}")
        try:
          current_move = game_board.push_san(move_input)
          invalid_move = False
        except IllegalMoveError as error:
          print('Invalid move!')
          invalid_move = True

      ai_turn = True
      move_count++

    is_game_ongoing = not game_board.is_game_over()




  
  

if __name__ == "__main__":
  menu_loop()