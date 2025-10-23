import chess
from dotenv import load_dotenv
import anthropic
import os
import sys
import time
from websockets.sync.client import connect
import websockets

load_dotenv()
primary_model = os.getenv("MODEL")
secondary_model = os.getenv("SECONDARY_MODEL")
logging = True

client = anthropic.Anthropic()

def menu_loop():
  menu_dict = {
    "entry": "------------Welcome to Terminal Chess!------------",
    "barrier": "***********************************************",
    "op_1": "1. Find an opponent online.",
    "op_2": "2. Play locally against a LLM.",
    "op_3": "3. Pit 2 LLMs against each other."
  }

  for entry in menu_dict.values():
    print(entry)
  
  user_selection = input()
  while user_selection not in ['1', '2', '3']:
    user_selection = input("Please select a valid option!")
    print(menu_dict['op_1'])
    print(menu_dict['op_2'])
    print(menu_dict['op_3'])

  if user_selection == '1':
    game_result = run_game()
  elif user_selection == '2':
    game_result = run_LLM_game()
  elif user_selection == '3':
    game_result = spectate_LLM_game()

  play_again_input = input("Thank you for playing! Would you like to play again? (Y/N)")
  if play_again_input.lower() == 'y':
    menu_loop()
  else: 
    sys.exit(0)
  
# Finds a game online using simple matchmaking

def run_game() -> int:
  game_board = chess.Board()

  with connect("ws://localhost:8080") as ws:
    queue_type = input("Would you like to queue into quickplay or normal games? (quickplay/normal)")
    while queue_type.lower() not in ['quickplay', 'normal']:
      queue_type = input("Please enter a valid option! (quickplay/normal)")
    ws.send(queue_type)

    success_msg = ws.recv()
    player_color = success_msg.split(" ")[-1]
    print(f"Player {player_color} is connected!")
    is_player_turn = True if player_color == 'White' else False

    while(not game_board.is_game_over()):
      if is_player_turn:
        print(game_board)
        move_input = input("Enter a move in valid chess algebraic notation.")
        invalid_move = True

        while(invalid_move):
          try:
            current_move = game_board.push_san(move_input)
            invalid_move = False
          except (chess.IllegalMoveError, chess.InvalidMoveError) as error:
            print('Invalid move!')
            move_input = input("Enter a move in valid chess algebraic notation.")
            invalid_move = True

        print("\n")      
        ws.send(current_move.uci())
        is_player_turn = False
      else:
        move_input = ws.recv()
        print(move_input)
        if move_input.lower() == 'opponent timed out':
          return
        game_board.push(chess.Move.from_uci(move_input))
        print(game_board)
        print(f"Last move: {move_input}")
        is_player_turn = True      

  return 0

def gen_llm_move(board_state: chess.Board, side: str, given_model: str) -> chess.Move:
  base_prompt = f"You are playing a chess game on side: {side}. "

  # Build list of this side's current pieces
  is_white = (side.lower() == 'white')
  piece_map = board_state.piece_map()

  pieces = {}
  for square, piece in piece_map.items():
    if piece.color == chess.WHITE and is_white:
      piece_name = piece.symbol().upper()
      square_name = chess.square_name(square)
      if piece_name not in pieces:
        pieces[piece_name] = []
      pieces[piece_name].append(square_name)
    elif piece.color == chess.BLACK and not is_white:
      piece_name = piece.symbol().lower()
      square_name = chess.square_name(square)
      if piece_name not in pieces:
        pieces[piece_name] = []
      pieces[piece_name].append(square_name)

  if pieces:
    piece_list = []
    for piece_type, squares in sorted(pieces.items()):
      piece_list.append(f"{piece_type}: {', '.join(sorted(squares))}")
    base_prompt += f"Your current pieces: {'; '.join(piece_list)}. Do not move any pieces that aren't in this list."

  # Build list of this side's previous moves
  if len(board_state.move_stack) > 0:
    # White plays on even indices (0, 2, 4...), black on odd (1, 3, 5...)
    start_index = 0 if is_white else 1

    side_moves = []
    for i in range(start_index, len(board_state.move_stack), 2):
      move_number = (i // 2) + 1
      side_moves.append(f"{move_number}. {board_state.move_stack[i].uci()}")

    if side_moves:
      base_prompt += f"Your previous moves: {', '.join(side_moves)}. "

    base_prompt += f"The last move played was {board_state.peek()}. "
  else:
    base_prompt += "This is the first move. "

  base_prompt += f"The current state of the board is:\n{board_state}\n"
  base_prompt += "Generate a move in the form of chess algebraic notation for your next move, and nothing else."

  attempt_count = 0
  error_feedback = ""
  failed_moves = []

  while attempt_count < 6: # Set a maximum attempt count to prevent wasting tokens on too many different attempts.
    attempt_count += 1
    prompt = base_prompt + error_feedback
    if logging:
      with open('game.txt', 'a') as f:
        f.write(prompt)
        f.write("\n")

    try:
      model_resp = client.messages.create(
        model = given_model,
        max_tokens = 8,
        messages = [
          {'role': 'user', 'content': prompt},
          {'role': 'assistant', 'content': "I need to respond in only standard chess notation (SAN) with a maximum length of 5 characters, so my next move is:"}
        ]
      )

      resp_dict = model_resp.model_dump() if hasattr(model_resp, 'model_dump') else model_resp.__dict__
      if resp_dict.get('type') == 'error':
        print(f"Error: {resp_dict.get('error', {}).get('message')}")
        exit(1)
      else:
        model_move_string = resp_dict['content'][0]['text'].strip()
        if logging:
          with open('game.txt', 'a') as f:
            f.write(model_move_string)
            f.write("\n")
        if len(model_move_string) > 5:
          error_feedback = f"\nYour previous response '{model_move_string}' was too long. Provide only the move notation."
          continue

        generated_move = board_state.push_san(model_move_string)
        board_state.pop()  # Remove the move so we can return it instead
        return generated_move
    except chess.IllegalMoveError as illegal_move:
      failed_moves.append(model_move_string)
      failed_list = ", ".join(failed_moves)
      error_feedback = f"\nYour previous move '{model_move_string}' was illegal: {str(illegal_move)}. Failed moves so far: [{failed_list}]. Please generate a different legal move."
      print(f"Attempt {attempt_count}: Illegal move '{model_move_string}', retrying...")
      time.sleep(0.25)
    except Exception as model_response_fail:
      if 'model_move_string' in locals():
        failed_moves.append(model_move_string)
        failed_list = ", ".join(failed_moves)
        error_feedback = f"\nYour previous response '{model_move_string}' caused an error: {str(model_response_fail)}. Failed moves so far: [{failed_list}]. Please provide a valid move in algebraic notation."
      else:
        error_feedback = f"\nYour previous response caused an error: {str(model_response_fail)}. Please provide a valid move in algebraic notation."
      print(f"Attempt {attempt_count}: {model_response_fail}")
      time.sleep(0.25)

  return None


# Runs a game vs. a selected LLM locally

def run_LLM_game():

  move_count = 0
  player_side = input("Pick the side you want to play.\n")

  while player_side.lower() not in ['black', 'white']:
    player_side = input("Valid choices are: black, white")

  ai_side = 'black' if player_side == 'white' else 'white'
  ai_turn = True if player_side == 'black' else False

  is_game_ongoing = True
  game_board = chess.Board()

  while(is_game_ongoing):
    if ai_turn:
      current_move = gen_llm_move(game_board, ai_side, primary_model)
      game_board.push(current_move)
      ai_turn = False
      move_count += 1
    else:
      move_input = input("Enter a move in valid chess algebraic notation.")
      invalid_move = True

      while(invalid_move):
        try:
          current_move = game_board.push_san(move_input)
          invalid_move = False
        except IllegalMoveError as error:
          print('Invalid move!')
          invalid_move = True

      print("\n")
      print(game_board)
      print(f"Last move: {game_board.peek()}")
      print(move_count)
      ai_turn = True
      move_count += 1

    is_game_ongoing = not game_board.is_game_over()


def spectate_LLM_game():

  if logging:
    with open('game.txt', 'w') as f:
      f.write("START OF GAME\n")

  move_count = 0
  is_game_ongoing = True
  game_board = chess.Board()
  diff_model = True if secondary_model is not None else False

  side_1 = 'white'
  side_2 = 'black'

  while(is_game_ongoing):


    print("\n\n")
    print(f"-{primary_model}-")
    print(game_board)
    if diff_model:
      print(f"-{secondary_model}-")
    else:
      print(f"-{primary_model}-")

    if move_count % 2 == 0:
      current_move = gen_llm_move(game_board, side_1, primary_model)
      game_board.push(current_move)
    else:
      if diff_model:
        current_move = gen_llm_move(game_board, side_2, secondary_model)
      else:
        current_move = gen_llm_move(game_board, side_2, primary_model)
      game_board.push(current_move)

    move_count += 1
    print(move_count)
    if logging:
      with open('game.txt', 'a') as f:
        f.write(f"{move_count}. {game_board.peek()}\n")
        f.write("\n")
    is_game_ongoing = not game_board.is_game_over()
  

  
if __name__ == "__main__":
  menu_loop()

