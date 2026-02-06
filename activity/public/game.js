function getDiscordAvatarURL(user) {
    const format = user.avatar.startsWith("a_") ? "gif" : "png"; // animated or static
    const size = 32; // you can use 32, 64, 128, 256, 512, 1024, 2048
    return `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.${format}?size=${size}`;
}

function position(x, y, z) {
    return {
            x:  x*positioning.x.x +
                y*positioning.y.x +
                z*positioning.z.x,
            y:  x*positioning.x.y +
                y*positioning.y.y +
                z*positioning.z.y
        }
    }

function reversePosition(x, y) {
    return {
        x: (x*reversePositioning.x.x+y*reversePositioning.x.y)/reversePositioning.x.divisor,
        y: (x*reversePositioning.y.x+y*reversePositioning.y.y)/reversePositioning.y.divisor
    }
}

class World {
    constructor(id) {
        this.id = id;
        this.draw = this.draw.bind(this); // Bug fix, because `this` is not bound if used in requestAnimationFrame
        this.visible = {sizes: {minX: 0, maxX: -1, minY: 0, maxY: -1}, values: new Map(), order: []}
    }

    draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (keys["w"] || keys["arrowup"]) camera.y+=10;
        if (keys["s"] || keys["arrowdown"]) camera.y-=10;
        if (keys["a"] || keys["arrowleft"]) camera.x-=10;
        if (keys["d"] || keys["arrowright"]) camera.x+=10;

        this.clipChunks()
        for (const chunkId of this.visible.order) {
            const chunk = this.visible.values.get(chunkId)
            if (chunk.visible) chunk.draw();
        }
        requestAnimationFrame(this.draw);
    }

    clipChunks() {
        // all here is looking at y=0, with a bit of buffer
        const topleft = reversePosition(camera.x, camera.y);
        const topright = reversePosition(camera.x+camera.width, camera.y);
        const bottomleft = reversePosition(camera.x, camera.y+camera.height);
        const bottomright = reversePosition(camera.x+camera.width, camera.y+camera.height);
        const minX = Math.round(Math.min(topleft.x, topright.x, bottomleft.x, bottomright.x)/chunkSize-2);
        const maxX = Math.round(Math.max(topleft.x, topright.x, bottomleft.x, bottomright.x)/chunkSize+2);
        const minY = Math.round(Math.min(topleft.y, topright.y, bottomleft.y, bottomright.y)/chunkSize-2);
        const maxY = Math.round(Math.max(topleft.y, topright.y, bottomleft.y, bottomright.y)/chunkSize+2);
        const keyGen = (x, y) => {return `${x},${y}`}
        // expand left
        for (let x=this.visible.sizes.minX; minX<this.visible.sizes.minX; x--) {
            for (let y=this.visible.sizes.minY; y <= this.visible.sizes.maxY; y++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk === undefined) {
                    chunk = new Chunk(x, y, this.id);
                    chunk.load();
                    this.visible.values.set(keyGen(x, y), chunk);
                }
                chunk.startDisplay(this.visible);
            }
            this.visible.sizes.minX--;
        }
        // expand right
        for (let x=this.visible.sizes.maxX; maxX>this.visible.sizes.maxX; x++) {
            for (let y=this.visible.sizes.minY; y <= this.visible.sizes.maxY; y++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk === undefined) {
                    chunk = new Chunk(x, y, this.id);
                    chunk.load();
                    this.visible.values.set(keyGen(x, y), chunk);
                }
                chunk.startDisplay(this.visible);
            }
            this.visible.sizes.maxX++;
        }
        // expand down
        for (let y=this.visible.sizes.minY; minY<this.visible.sizes.minY; y--) {
            for (let x=this.visible.sizes.minX; x <= this.visible.sizes.maxX; x++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk === undefined) {
                    chunk = new Chunk(x, y, this.id);
                    chunk.load();
                    this.visible.values.set(keyGen(x, y), chunk);
                }
                chunk.startDisplay(this.visible);
            }
            this.visible.sizes.minY--;
        }
        // expand up
        for (let y=this.visible.sizes.maxY; maxY>this.visible.sizes.maxY; y++) {
            for (let x=this.visible.sizes.minX; x <= this.visible.sizes.maxX; x++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk === undefined) {
                    chunk = new Chunk(x, y, this.id);
                    chunk.load();
                    this.visible.values.set(keyGen(x, y), chunk);
                }
                chunk.startDisplay(this.visible);
            }
            this.visible.sizes.maxY++;
        }
        // contract left
        for (let x=this.visible.sizes.minX; minX>this.visible.sizes.minX; x++) {
            for (let y=this.visible.sizes.minY; y <= this.visible.sizes.maxY; y++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk !== undefined) chunk.stopDisplay(this.visible);
            }
            this.visible.sizes.minX++;
        }
        // contract right
        for (let x=this.visible.sizes.maxX; maxX<this.visible.sizes.maxX; x--) {
            for (let y=this.visible.sizes.minY; y <= this.visible.sizes.maxY; y++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk !== undefined) chunk.stopDisplay(this.visible);
            }
            this.visible.sizes.maxX--;
        }
        // contract down
        for (let y=this.visible.sizes.minY; minY>this.visible.sizes.minY; y++) {
            for (let x=this.visible.sizes.minX; x <= this.visible.sizes.maxX; x++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk !== undefined) chunk.stopDisplay(this.visible);
            }
            this.visible.sizes.minY++;
        }
        // contract up
        for (let y=this.visible.sizes.maxY; maxY<this.visible.sizes.maxY; y--) {
            for (let x=this.visible.sizes.minX; x <= this.visible.sizes.maxX; x++) {
                let chunk = this.visible.values.get(keyGen(x, y));
                if (chunk !== undefined) chunk.stopDisplay(this.visible);
            }
            this.visible.sizes.maxY--;
        }
    }
}

class Chunk {
    constructor(x, y, world) {
        this.x = x;
        this.y = y;
        this.world = world;
        this.key = 9_999_999_999 - this.x - this.y*100_000;
        this.blocks = [];
        this.visible = false;
        this.tiles = new Map();
        this.tileOrder = [];
        this.image = new Image();
        this.imageloaded = false;
        this.blocksChanged = false;
    }

    async load() {
        console.log(`Loading Chunk at ${this.x} ${this.y}`)
        const res = await fetch(`chunks/${this.world}/${this.x}_${this.y}.json`);
        if (!res.ok) return;
        const data = await res.json();

        let z = 0;

        for (const layer of data.layers) {
            for (let y = 0; y < layer.length; y++) {
                const line = layer[y];
                for (let x = 0; x < line.length; x++) {
                    const block = line[x];
                    this.blocks.push(new Block(x, y, z, block));
                }
            }
            z++;
        }
        this.blocksChanged = true;
        console.log(`Successfully loaded Chunk at ${this.x} ${this.y}`)
    }

    render() {
        console.log(`Rendering Chunk at ${this.x} ${this.y}`)
        this.blocksChanged = false;
        this.imageloaded = true;
        this.tiles.clear();
        this.tileOrder = [];
        this.blocks.forEach(block => {
            this.tiles.set(block.key, block);
            let lo = 0, hi = this.tileOrder.length;
            while (lo < hi) {
                const mid = (lo + hi) >> 1;
                if (this.tileOrder[mid] < block.key) lo = mid+1;
                else hi = mid;
            }
            this.tileOrder.splice(lo, 0, block.key);
        });
        for (let key of this.tileOrder) {
            this.tiles.get(key).draw()
        }
        tmpCtx.clearRect(0, 0, 1000, 1000)
        for (const blockId of this.tileOrder) {
            const block = this.tiles.get(blockId);
            block.draw();
        }
        this.image.src = tmpCanvas.toDataURL();
    }

    draw() {
        if (this.blocksChanged && this.visible) this.render();
        const pos = position(this.x*chunkSize, 0, this.y*chunkSize)
        ctx.drawImage(this.image, pos.x-camera.x-250, pos.y+camera.y+250)
    }

    startDisplay(visibleInfo) {
        console.log(`Start display chunk ${this.x} ${this.y}`);
        if (this.blocksChanged) {
            this.render();
        }
        visibleInfo.values.set(this.key, this);
            let lo = 0, hi = visibleInfo.order.length;
            while (lo < hi) {
                const mid = (lo + hi) >> 1;
                if (visibleInfo.order[mid] < this.key) lo = mid+1;
                else hi = mid;
            }
        visibleInfo.order.splice(lo, 0, this.key);
        this.visible = true;
    }

    stopDisplay(visibleInfo) {
        console.log(`Stop display chunk ${this.x} ${this.y}`);
        this.visible = false;
    }

}

class Block {
    constructor(x, y, z, id) {
        this.x = x;
        this.y = y;
        this.z = z;
        this.key = 9_999_999_999 - this.x - this.y*100_000 + this.z*10_000_000_000;
        this.position = position(x, y, z)
        this.imageCrop = {
            x: 64*((id-1)%8),
            y: 64*Math.floor((id-1)/8),
            w: 64,
            h: 64
        };
    }

    draw() {
        console.log(`drawing block at ${this.x}, ${this.y}, ${this.z}`)
        tmpCtx.drawImage(
            tileMap, this.imageCrop.x, this.imageCrop.y, this.imageCrop.w, this.imageCrop.h,
            this.position.x+500, this.position.y+500, this.imageCrop.w, this.imageCrop.h
        );
    }
}

const canvas = document.getElementById("canvas");
const tmpCanvas = document.getElementById("tmpCanvas");
const ctx = canvas.getContext("2d");
const tmpCtx = tmpCanvas.getContext("2d");
const keys = {};
const tileMap = new Image();
const entityMap = new Image();
const world = new World("testworld");
const chunkSize = 8;
const positioning = {
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
const reversePositioning = {
    x: {
        x: 11,
        y: -4,
        divisor: 421
    },
    y: {
        x: 3,
        y: 35,
        divisor: 1263
    }
}
let user;
let camera = { x: 0, y: 0, width: 0, height: 0 };
let gamepads = {};
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
camera.width = window.innerWidth;
camera.height = window.innerHeight;
tmpCanvas.width = 1000;
tmpCanvas.height = 1000;
tileMap.src = "assets/tiles.png";
entityMap.src = "assets/entities.png";


fetch("/api/me", { credentials: "include" })
    .then(res => res.json())
    .then(data => {
        if (!data) throw ReferenceError("The user was not found!");
        user = data;
    });

const player = { x: 100, y: 100, dx: 0, dy: 0, speed: 200, sprite: null, playerGif: null, playerGifInfo: null, animationTimer: 0 };

// Load sprite
// const playerImg = new Image();
// playerImg.src = getDiscordAvatarURL(user);
// playerImg.onload = () => { player.sprite = playerImg; };
// const playerGif = new Image();
// playerGif.src = "assets/player.png";
// playerGif.onload = () => { player.playerGif = playerGif; };
// fetch("assets/player.json")
//     .then(data => data.json())
//     .then(data => {player.playerGifInfo = data;});

// Event listeners
window.addEventListener("keydown", (e) => {
    keys[e.key.toLowerCase()] = true;
});

window.addEventListener("keyup", (e) => {
    keys[e.key.toLowerCase()] = false;
});

window.addEventListener("gamepadconnected", (e) => {
    console.log("Gamepad connected:", e.gamepad);
    gamepads[e.gamepad.index] = e.gamepad;
});

window.addEventListener("gamepaddisconnected", (e) => {
    console.log("Gamepad disconnected:", e.gamepad);
    delete gamepads[e.gamepad.index];
});

window.addEventListener("resize", () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    camera.width = window.innerWidth;
    camera.height = window.innerHeight;
});



// function drawRoundAvatar(ctx, img, x, y, size) {
//     ctx.save(); // Save the current canvas state

//     // Create a circular clipping region
//     ctx.beginPath();
//     ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2);
//     ctx.closePath();
//     ctx.clip();

//     // Draw the avatar image inside the clipped circle
//     ctx.drawImage(img, x, y, size, size);

//     ctx.restore(); // Restore canvas state
// }



// // Game loop
// let lastTime = 0;
// function gameLoop(timestamp) {
//     const dTime = (timestamp - lastTime) / 1000; // seconds
//     lastTime = timestamp;


//     ctx.clearRect(0, 0, canvas.width, canvas.height);

//     player.dx = 0;
//     player.dy = 0;
//     if (keys["w"] || keys["arrowup"]) player.dy = -player.speed;
//     if (keys["s"] || keys["arrowdown"]) player.dy = player.speed;
//     if (keys["a"] || keys["arrowleft"]) player.dx = -player.speed;
//     if (keys["d"] || keys["arrowright"]) player.dx = player.speed;

//     const gps = navigator.getGamepads();
//     for (const gp of gps) {
//         if (!gp) continue;

//         // Example: move player with left stick
//         const [xAxis, yAxis] = [gp.axes[0], gp.axes[1]];

//         if (Math.abs(xAxis) > 0.1) player.dx = xAxis * player.speed;
//         if (Math.abs(yAxis) > 0.1) player.dy = yAxis * player.speed;
//     }

//     player.x += player.dx * dTime
//     player.y += player.dy * dTime

//     let block1 = new Block(0, -1, 0, 1)
//     let block3 = new Block(0, -2, 0, 1)
//     let block4 = new Block(1, -2, 0, 1)
//     let block5 = new Block(1, -1, 1, 1)

//     // Draw tiles
//     block1.draw(ctx);
//     block4.draw(ctx);
//     block3.draw(ctx);
//     block5.draw(ctx);

//     // Draw player
//     if (player.sprite) {
//         drawRoundAvatar(ctx, player.sprite, player.x+18, player.y+18, 64)
//     }
//     if (player.playerGif && player.playerGifInfo) {
//         if (player.dx !== 0 || player.dy !== 0) {
//             player.animationTimer += dTime * 1000;
//         }
//         const frame = Math.floor((player.animationTimer / player.playerGifInfo.frametime) % player.playerGifInfo.frames )
//         ctx.drawImage(
//             player.playerGif,
//             0,
//             player.playerGifInfo.height * frame,
//             player.playerGifInfo.width,
//             player.playerGifInfo.height,
//             player.x,
//             player.y,
//             player.playerGifInfo.width,
//             player.playerGifInfo.height
//         )
//     }
//     ctx.font = "20px Arial";
//     ctx.fillText(user.username, player.x+50-(ctx.measureText(user.username).width/2), player.y);

//     requestAnimationFrame(gameLoop);
// }

requestAnimationFrame(world.draw);