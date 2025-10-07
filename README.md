# CropWise – Real-Time (Dynamic) Setup

## Backend
cd "C:\\Users\\kasya\\OneDrive\\Documents\\Crop Calendar\\BACK END"
pip install -r requirements.txt
set OPENWEATHER_API_KEY=YOUR_OPENWEATHER_KEY
uvicorn main:app --reload

## Frontend
cd "C:\\Users\\kasya\\OneDrive\\Documents\\Crop Calendar\\FRONT END (ReactJS)"
npm install
npm run dev

### Notes
- Use `/geocode?query=Guntur` to search any place (state/UT/city/district)
- `/states` returns cached recent places
- Admin crop rules: GET/POST/PUT/DELETE /admin/crop_rules
- First user (or username `admin`) becomes admin
