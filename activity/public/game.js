const user = (await (await fetch("/api/me", { credentials: "include" })).json()).user;

if (!user) {
    throw ReferenceError("The user was not found!");
}


function getDiscordAvatarURL(user) {
    const format = user.avatar.startsWith("a_") ? "gif" : "png"; // animated or static
    const size = 64; // you can use 32, 64, 128, 256, 512, 1024, 2048
    return `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.${format}?size=${size}`;
}

class World {
    constructor() {
        this.chunks = [];
        this.tiles = new Map();
        this.tileOrder = [];

        this.animate = this.animate.bind(this); // Bug fix, because `this` is not bound if not used
    }

    animate() {
        for (const key of this.tileOrder) {
            this.tiles.get(key).draw();
        }
        requestAnimationFrame(this.animate);
    }
}

class Chunk {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.blocks = [];
    }

    async load() {
        const res = await fetch(`chunks/${this.x}_${this.y}.json`);
        const data = await res.json();

        const layerSize = 8;
        let z = 0;

        for (const layer of data.layers) {
            for (let y = 0; y < layer.length; y++) {
                const line = layer[y];
                for (let x = 0; x < line.length; x++) {
                    const block = line[x];
                    this.blocks.push(new Block(
                        layerSize * this.x + x,
                        layerSize * this.y + y,
                        z,
                        block
                    ));
                }
            }
            z++;
        }
    }

    addTiles(tiles, tileOrder) {
        this.blocks.forEach(block => {
            tiles.set(block.key, block)
            let lo = 0, hi = tileOrder.length;
            while (lo < hi) {
                const mid = (lo + hi) >> 1;
                if (tileOrder[mid] < block.key) lo = mid+1;
                else hi = mid;
            }
            tileOrder.splice(lo, 0, block.key);
        });
    }

    removeTiles(tiles, tileOrder) {
        this.blocks.forEach(block => {
            tiles.delete(block.key);
            let lo = 0, hi = tileOrder.length;
            while (lo < hi) {
                const mid = (lo + hi) >> 1;
                if (tileOrder[mid] < block.key) lo = mid + 1;
                else hi = mid;
            };
            tileOrder.splice(lo, 1);
        });
    }

}

class Block {
    constructor(x, y, z, blockId) {
        this.x = x;
        this.y = y;
        this.z = z;
        this.key = 9_999_999_999 - this.x - this.y*100_000 + this.z*10_000_000_000;
        this.imageCrop = {
            x: 64*((blockId-1)%8),
            y: 64*Math.floor((blockId-1)/8),
            w: 64,
            h: 64
        };
        this.positioning = {
            x: {
                x: 35,
                y: -9
            },
            y: {
                x: -12,
                y: -33
            },
            z: {
                x: 2,
                y: -22
            }
        };
    }

    position() {
        return {
            x:  this.x*this.positioning.x.x +
                this.y*this.positioning.y.x +
                this.z*this.positioning.z.x,
            y:  this.x*this.positioning.x.y +
                this.y*this.positioning.y.y +
                this.z*this.positioning.z.y
        }
    }

    draw() {
        const positioned = this.position();
        ctx.drawImage(
            tileMap, this.imageCrop.x, this.imageCrop.y, this.imageCrop.w, this.imageCrop.h,
            positioned.x, positioned.y, this.imageCrop.w, this.imageCrop.h
        );
    }
}

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

resizeCanvas();
window.addEventListener("resize", resizeCanvas);

const camera = { x: 0, y: 0 };
const player = { x: 100, y: 100, dx: 0, dy: 0, speed: 200, sprite: null, playerGif: null, playerGifInfo: null, animationTimer: 0 };

// Load sprite
const playerImg = new Image();
playerImg.src = getDiscordAvatarURL(user);
playerImg.onload = () => { player.sprite = playerImg; };
const playerGif = new Image();
playerGif.src = "assets/player.png";
playerGif.onload = () => { player.playerGif = playerGif; };
fetch("assets/player.json")
    .then(data => data.json())
    .then(data => {player.playerGifInfo = data;});
let tileMapLoaded = false
const tileMap = new Image();
tileMap.src = "assets/tiles.png";
tileMap.onload = () => { tileMapLoaded = true; };
const entityMap = new Image();
entityMap.src = "assets/entities.png";

const keys = {};

window.addEventListener("keydown", (e) => {
    keys[e.key.toLowerCase()] = true; // store the key as lowercase
});

window.addEventListener("keyup", (e) => {
    keys[e.key.toLowerCase()] = false;
});

let gamepads = {};

window.addEventListener("gamepadconnected", (e) => {
    console.log("Gamepad connected:", e.gamepad);
    gamepads[e.gamepad.index] = e.gamepad;
});

window.addEventListener("gamepaddisconnected", (e) => {
    console.log("Gamepad disconnected:", e.gamepad);
    delete gamepads[e.gamepad.index];
});



function drawRoundAvatar(ctx, img, x, y, size) {
    ctx.save(); // Save the current canvas state

    // Create a circular clipping region
    ctx.beginPath();
    ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2);
    ctx.closePath();
    ctx.clip();

    // Draw the avatar image inside the clipped circle
    ctx.drawImage(img, x, y, size, size);

    ctx.restore(); // Restore canvas state
}



// Game loop
let lastTime = 0;
function gameLoop(timestamp) {
    const dTime = (timestamp - lastTime) / 1000; // seconds
    lastTime = timestamp;


    ctx.clearRect(0, 0, canvas.width, canvas.height);

    player.dx = 0;
    player.dy = 0;
    if (keys["w"] || keys["arrowup"]) player.dy = -player.speed;
    if (keys["s"] || keys["arrowdown"]) player.dy = player.speed;
    if (keys["a"] || keys["arrowleft"]) player.dx = -player.speed;
    if (keys["d"] || keys["arrowright"]) player.dx = player.speed;

    const gps = navigator.getGamepads();
    for (const gp of gps) {
        if (!gp) continue;

        // Example: move player with left stick
        const [xAxis, yAxis] = [gp.axes[0], gp.axes[1]];

        if (Math.abs(xAxis) > 0.1) player.dx = xAxis * player.speed;
        if (Math.abs(yAxis) > 0.1) player.dy = yAxis * player.speed;
    }

    player.x += player.dx * dTime
    player.y += player.dy * dTime

    let block1 = new Block(0, -1, 0, 1)
    let block3 = new Block(0, -2, 0, 1)
    let block4 = new Block(1, -2, 0, 1)
    let block5 = new Block(1, -1, 1, 1)

    // Draw tiles
    block1.draw(ctx);
    block4.draw(ctx);
    block3.draw(ctx);
    block5.draw(ctx);

    // Draw player
    if (player.sprite) {
        drawRoundAvatar(ctx, player.sprite, player.x+18, player.y+18, 64)
    }
    if (player.playerGif && player.playerGifInfo) {
        if (player.dx !== 0 || player.dy !== 0) {
            player.animationTimer += dTime * 1000;
        }
        const frame = Math.floor((player.animationTimer / player.playerGifInfo.frametime) % player.playerGifInfo.frames )
        ctx.drawImage(
            player.playerGif,
            0,
            player.playerGifInfo.height * frame,
            player.playerGifInfo.width,
            player.playerGifInfo.height,
            player.x,
            player.y,
            player.playerGifInfo.width,
            player.playerGifInfo.height
        )
    }
    ctx.font = "20px Arial";
    ctx.fillText(user.username, player.x+50-(ctx.measureText(user.username).width/2), player.y);

    requestAnimationFrame(gameLoop);
}
const world = new World()
const chunk1 = new Chunk(0, -2)
const chunk2 = new Chunk(1, -2)
chunk1.load().then(() => {
    chunk1.addTiles(world.tiles, world.tileOrder);
})
chunk2.load().then(() => {
    chunk2.addTiles(world.tiles, world.tileOrder);
})

requestAnimationFrame(world.animate);