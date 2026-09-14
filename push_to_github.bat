@echo off
chcp 65001 >nul
title Push PK Auto Edit Kit to GitHub
echo ======================================================
echo   PK Auto Edit Kit - Deploy to GitHub (pk-project-th)
echo ======================================================
echo.
echo กำลังดันโค้ดขึ้น https://github.com/pk-project-th/pk-auto-edit-kit...
echo.
git push -u origin main
echo.
if %errorlevel% equ 0 (
    echo ======================================================
    echo  SUCCESS: ดันโค้ดขึ้น GitHub เรียบร้อยแล้ว!
    echo  ไปที่ https://share.streamlit.io เพื่อกด Deploy ได้ทันที
    echo ======================================================
) else (
    echo ======================================================
    echo  เกิดข้อผิดพลาด กรุณาตรวจสอบการล็อกอิน GitHub
    echo ======================================================
)
echo.
pause
