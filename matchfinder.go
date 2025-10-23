package main

import (
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"
)

type player struct {
	id     string
	status string
	conn   *websocket.Conn
}

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

var (
	playerQueue []*player
	queueMutex  sync.Mutex
)

func checkForMatch() (*player, *player) {
	queueMutex.Lock()
	defer queueMutex.Unlock()

	if len(playerQueue) >= 2 {
		player_1 := playerQueue[0]
		player_2 := playerQueue[1]

		playerQueue = playerQueue[2:]

		player_1.status = "playing"
		player_2.status = "playing"

		log.Print("Match found! Player 1 is ", player_1.id, " and player 2 is ", player_2.id)
		return player_1, player_2
	}
	return nil, nil
}

func playGame(white *player, black *player) {
	currentTurn := white
	nextTurn := black
	for {
		messageType, currentMove, err := currentTurn.conn.ReadMessage()
		if err != nil {
			log.Print("Error reading message: ", err)
			return
		}
		if messageType != websocket.TextMessage {
			log.Print("Invalid message type: ", messageType)
			return
		}
		log.Print("Received move: ", string(currentMove))
		nextTurn.conn.WriteMessage(websocket.TextMessage, currentMove)
		if currentTurn == white {
			currentTurn = black
			nextTurn = white
		} else {
			currentTurn = white
			nextTurn = black
		}
	}
}
func main() {
	fmt.Println("Starting matchfinder...")

	matchfinderHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			log.Print("upgrade:", err)
			return
		}

		p := &player{
			id:     uuid.NewString(),
			status: "waiting",
			conn:   conn,
		}

		log.Print("New player connected: ", p.id)
		queueMutex.Lock()
		playerQueue = append(playerQueue, p)
		queueMutex.Unlock()

		player1, player2 := checkForMatch()

		if player1 != nil && player2 != nil {
			player1.conn.WriteMessage(websocket.TextMessage, []byte("Match found! Your color is: White"))
			player2.conn.WriteMessage(websocket.TextMessage, []byte("Match found! Your color is: Black"))

			go playGame(player1, player2)
		}

	})

	matchfinder := &http.Server{
		Addr:           ":8080",
		Handler:        http.HandlerFunc(matchfinderHandler),
		ReadTimeout:    10 * time.Second,
		WriteTimeout:   10 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}

	matchfinder.ListenAndServe()
}
