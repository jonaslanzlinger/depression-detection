const express = require("express");
const http = require("http");
const cors = require("cors");
const { Server } = require("socket.io");

const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const io = new Server(server, {
   cors: {
      origin: "*",
   },
});

io.on("connection", (socket) => {
   console.log("client connected");

   socket.on("disconnect", () => {
      console.log("client disconnected");
   });
});

app.post("/speech_metrics", (req, res) => {
   const data = req.body;
   console.log("Received from audio-processor:", data);

   // emit socket message for the frontend
   io.emit("audio_to_frontend", data);

   res.status(200).send({ status: "ok" });
});

server.listen(5051, () => {
   console.log("WebSocket server running on http://localhost:5051");
});
