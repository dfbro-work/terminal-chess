import chess

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
    print(menu_dict[2])
    print(menu_dict[3])

  if user_selection == '1':
    game_result = run_game()
  elif user_selection == '2':
    game_result = run_LLM_game()

  play_again_input = input("Thank you for playing! Would you like to play again? (Y/N)")
  if play_again_input.lower() == 'y' menu_loop() else exit(0)
  

def gen_llm_move(board_state, side):
  return ""


def run_game():
  return 0

def run_LLM_game():
  player_side = input("Pick the side you want to play.")

  while player_side.lower() not in ['black', 'white']:
    player_side = input("Valid choices are: black, white")

  ai_side = 'black' if player_side == 'white' else 'white'
  ai_turn = True if player_side == 'black' else False

  is_game_ongoing = True
  game_board = chess.Board()

  while(is_game_ongoing):
    if ai_turn:
      current_move = gen_llm_move(game_board, ai_side)
      game_board.push_san(current_move)
      ai_turn = False
    else:
      move_input = input("Enter a move in valid chess algebraic notation.")
      invalid_move = True

      while(invalid_move):
        print(game_board)
        try:
          current_move = game_board.push_san(move_input)
          invalid_move = False
        except IllegalMoveError as error:
          print('Invalid move!')
          invalid_move = True

      ai_turn = True

    is_game_ongoing = not game_board.is_game_over()

   ## black move
    if ai_side == 'black':
      current_move = gen_llm_move(game_board)
      game_board.push_san(current_move)
    else:



  
  

if __name__ == "__main__":
  menu_loop()