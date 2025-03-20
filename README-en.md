
# Backend Flask Application with YOLO Object Recognition

This repository contains a Backend Flask application that integrates object recognition using the YOLO model. The YOLO model used in this project is `yolo_model/0317_best.pt`, which can be downloaded [here](https://github.com/graduateam/YOLO/blob/de480a760724c23bf275478c2f970919b13ba363/0317_best.pt).

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Model Information](#model-information)
- [Contributing](#contributing)
- [License](#license)

## Introduction

This project aims to provide a backend solution for object recognition tasks using the YOLO (You Only Look Once) model. The application is built using Flask, a lightweight WSGI web application framework for Python.

## Features

- Object recognition using YOLO model
- RESTful API for image uploads and predictions
- Easy to integrate with other applications

## Installation

To get started with this project, follow the steps below:

1. Clone the repository:

    ```bash
    git clone https://github.com/viincci/Backend-Flask.git
    cd Backend-Flask
    ```

2. Create a virtual environment and activate it:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Download the YOLO model and place it in the appropriate directory:

    ```bash
    mkdir -p yolo_model
    wget -O yolo_model/0317_best.pt https://github.com/graduateam/YOLO/blob/de480a760724c23bf275478c2f970919b13ba363/0317_best.pt
    ```

## Usage

To run the Flask application, use the following command:

```bash
flask run
```

The application will start on `http://127.0.0.1:5000/`. You can use tools like Postman or cURL to interact with the API.

## Model Information

The YOLO model used in this project is `0317_best.pt`. This model is trained for object recognition tasks and can be downloaded from [this link](https://github.com/graduateam/YOLO/blob/de480a760724c23bf275478c2f970919b13ba363/0317_best.pt).

## Contributing

Contributions are welcome! If you have any ideas, suggestions, or bug reports, please open an issue or submit a pull request.

### Contributors

- [viincci](https://github.com/viincci)
- [GraduaTeam](https://github.com/graduateam) 

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

---

Feel free to modify the content as needed. Let me know if there is anything else you would like to add or change!
