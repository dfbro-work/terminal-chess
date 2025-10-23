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
	quickplayQueue []*player
	normalQueue    []*player
	queueMutex     sync.Mutex
)

func checkForMatch() (*player, *player, string) {
	queueMutex.Lock()
	defer queueMutex.Unlock()

	if len(quickplayQueue) >= 2 {
		player_1 := quickplayQueue[0]
		player_2 := quickplayQueue[1]

		quickplayQueue = quickplayQueue[2:]

		player_1.status = "playing"
		player_2.status = "playing"

		matchType := "quickplay"
		log.Print("Match found in ", matchType, " queue! Player 1 is ", player_1.id, " and player 2 is ", player_2.id)
		return player_1, player_2, matchType

	} else if len(normalQueue) >= 2 {
		player_1 := normalQueue[0]
		player_2 := normalQueue[1]

		normalQueue = normalQueue[2:]

		player_1.status = "playing"
		player_2.status = "playing"

		matchType := "normal"
		log.Print("Match found in ", matchType, " queue! Player 1 is ", player_1.id, " and player 2 is ", player_2.id)
		return player_1, player_2, matchType
	}

	return nil, nil, ""
}

func normalGame(white *player, black *player) {
	currentTurn := white
	nextTurn := black

	for {
		messageType, currentMove, err := currentTurn.conn.ReadMessage()
		if err != nil {
			log.Print("Error reading message: ", err)
			return
		}
		if messageType == websocket.TextMessage {

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

}
func quickplayGame(white *player, black *player) {
	currentTurn := white
	nextTurn := black

	for {
		timeout := time.After(time.Second * 60)
		moveChan := make(chan []byte)

		go func() {
			_, message, err := currentTurn.conn.ReadMessage()
			if err == nil {
				moveChan <- message
			}
		}()

		select {
		case <-timeout:
			log.Print("Timeout reached for player ", nextTurn.id)
			// Send close frame to the player who timed out (with custom close code)
			nextTurn.conn.WriteControl(websocket.CloseMessage,
				websocket.FormatCloseMessage(4000, "You timed out"),
				time.Now().Add(time.Second))
			nextTurn.conn.Close()

			// Send close frame to the opponent (who won)
			currentTurn.conn.WriteControl(websocket.CloseMessage,
				websocket.FormatCloseMessage(4001, "Opponent timed out"),
				time.Now().Add(time.Second))
			currentTurn.conn.Close()

			white.status = "waiting"
			black.status = "waiting"

			return
		case move := <-moveChan:
			log.Print("Received move: ", string(move))
			nextTurn.conn.WriteMessage(websocket.TextMessage, move)
			if currentTurn == white {
				currentTurn = black
				nextTurn = white
			} else {
				currentTurn = white
				nextTurn = black
			}
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

		_, queueType, err := p.conn.ReadMessage()
		if err != nil {
			log.Print("Error reading message: ", err)
			return
		}
		if string(queueType) == "quickplay" {
			log.Print("New player connected to quickplay queue: ", p.id)
			queueMutex.Lock()
			quickplayQueue = append(quickplayQueue, p)
			queueMutex.Unlock()
		} else if string(queueType) == "normal" {
			log.Print("New player connected to normal queue: ", p.id)
			queueMutex.Lock()
			normalQueue = append(normalQueue, p)
			queueMutex.Unlock()
		}

		player1, player2, matchType := checkForMatch()

		if player1 != nil && player2 != nil {
			player1.conn.WriteMessage(websocket.TextMessage, []byte("Match found! Your color is: White"))
			player2.conn.WriteMessage(websocket.TextMessage, []byte("Match found! Your color is: Black"))

			if matchType == "quickplay" {
				go quickplayGame(player1, player2)
			} else if matchType == "normal" {
				go normalGame(player1, player2)
			}
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
