const express = require("express");
const app = express();

const http = require("http");
const server = http.createServer(app);

const { Server } = require("socket.io");
const io = new Server(server);

app.get("/", (req, res) => {
  res.sendFile(__dirname + "/index.html");
});
app.use(express.static(__dirname + "/assets"));

server.listen(3000, () => {
  console.log("Listening on port 3000");
});

io.of("/jetbot").on("connection", (socket) => {
  console.log("User connected");

  socket.on("disconnect", () => {
    io.of("/jetbot").emit("disconnect1", {name:'bobo Thuan'});
    console.log(`User disconnected`);
  });

  socket.on("jetbot", (data) => {
    // console.log(data)
    io.of("/jetbot").emit("web", data);
  });

});
