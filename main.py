import flet as ft

def main(page: ft.Page):
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    page.add(
        ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN, size=100),
        ft.Text("SUCCESS! The app engine is working!", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_800)
    )

ft.app(main)
