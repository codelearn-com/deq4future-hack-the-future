#!/usr/bin/python3

# Copyright 2025 CODELEARN SL (MIT License)
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest
import pymysql
import os
import random
import datetime
import json
import time

# I do this to accept all methods and give custom errors
HTTP_METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH']
# More info: https://stackoverflow.com/a/57022994/9643618

app = Flask(__name__)

def get_db():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "db"),
        user=os.getenv("DB_USER", "user"),
        password=os.getenv("DB_PASS", "password"),
        database=os.getenv("DB_NAME", "gamesdb"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
    return conn

def create_schema():
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Game (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                seed INT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finalized_at DATETIME DEFAULT NULL,
                latest_update_at DATETIME DEFAULT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS GameUpdate (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                game_id BIGINT,
                sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                data TEXT NOT NULL,
                FOREIGN KEY (game_id) REFERENCES Game(id)
            );
        """)
    conn.close()

@app.route("/game/new", methods=HTTP_METHODS)
def new_game():
    if request.method != "GET":
        return jsonify({"ok": False, "reason": "This endpoint accepts only GET requests"}), 400

    seed = random.randint(10000, 99999)

    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO Game (seed) VALUES (%s)
        """, (seed,))
        game_id = cursor.lastrowid
    conn.close()

    return jsonify({"game_id": game_id, "seed": seed})

@app.route("/game/store_progress", methods=HTTP_METHODS)
def store_progress():
    if request.method != "POST":
        return jsonify({"ok": False, "reason": "This endpoint accepts only POST requests"}), 400

    try:
        data = request.get_json(force=True)
    except BadRequest:
        return jsonify({
            "ok": False,
            "reason": "JSON formatting error"
        }), 415

    game_id = data.get("game_id")
    progress_data = data.get("data")

    if not game_id or progress_data is None:
        return jsonify({"ok": False, "reason": "Missing game_id or data"}), 415

    conn = get_db()
    with conn.cursor() as cursor:
        # Check if game exists
        cursor.execute("SELECT * FROM Game WHERE id = %s", (game_id,))
        game = cursor.fetchone()
        if not game:
            return jsonify({"ok": False, "reason": "Game ID not found"}), 404

        if game["finalized_at"] is not None:
            return jsonify({"ok": False, "reason": "This game is already finalized"}), 409

        progress_json = json.dumps(progress_data)
        if len(progress_json) > 100_000:
            return jsonify({
                "ok": False,
                "reason": "Data too large, must be under 100,000 characters"
            }), 413

        cursor.execute("""
            INSERT INTO GameUpdate (game_id, data)
            VALUES (%s, %s)
        """, (game_id, progress_json))

        cursor.execute("""
            UPDATE Game SET latest_update_at = %s WHERE id = %s
        """, (datetime.datetime.utcnow(), game_id))
    conn.close()

    return jsonify({"ok": True, "game_id": game_id})

@app.route("/game/finalize", methods=HTTP_METHODS)
def finalize_game():
    if request.method != "POST":
        return jsonify({"ok": False, "reason": "This endpoint accepts only POST requests"}), 400

    try:
        data = request.get_json(force=True)
    except BadRequest:
        return jsonify({
            "ok": False,
            "reason": "JSON formatting error"
        }), 415
    
    game_id = data.get("game_id")
    final_data = data.get("data")
    score = data.get("score")

    if not game_id or final_data is None or score is None:
        return jsonify({"ok": False, "reason": "Missing fields"}), 415

    conn = get_db()
    with conn.cursor() as cursor:
        # Check if game exists
        cursor.execute("SELECT * FROM Game WHERE id = %s", (game_id,))
        game = cursor.fetchone()
        if not game:
            return jsonify({"ok": False, "reason": "Game ID not found"}), 404
        
        if game["finalized_at"] is not None:
            return jsonify({"ok": False, "reason": "This game is already finalized"}), 409

        progress_json = json.dumps(final_data)
        if len(progress_json) > 100_000:
            return jsonify({
                "ok": False,
                "reason": "Data too large, must be under 100,000 characters"
            }), 413

        cursor.execute("""
            INSERT INTO GameUpdate (game_id, data)
            VALUES (%s, %s)
        """, (game_id, progress_json))

        # Finalize game
        cursor.execute("""
            UPDATE Game SET finalized_at = %s, latest_update_at = %s
            WHERE id = %s
        """, (datetime.datetime.utcnow(), datetime.datetime.utcnow(), game_id))
    conn.close()

    return jsonify({"ok": True, "game_id": game_id})

@app.route("/game/get_progress", methods=HTTP_METHODS)
def get_progress():
    if request.method != "GET":
        return jsonify({"ok": False, "reason": "This endpoint accepts only GET requests"}), 400

    game_id = request.args.get("game_id", type=int)
    if not game_id:
        return jsonify({"ok": False, "reason": "Missing game_id"}), 400

    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT data FROM GameUpdate WHERE game_id = %s
            ORDER BY sent_at DESC LIMIT 1
        """, (game_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"ok": False, "reason": "No progress found"}), 404

    return jsonify({"ok": True, "game_id": game_id, "data": json.loads(row["data"])})

# Running in production (gunicorn) makes it skip the __name__=="__main__" stuff.
time.sleep(10) # Waiting DB to boot
create_schema()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3555)
