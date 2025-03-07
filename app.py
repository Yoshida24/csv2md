import streamlit as st
import csv
import io
import zipfile
import re
import pandas as pd
import time

st.set_page_config(page_title='CSV to Markdown Converter', layout='wide')
st.title('CSV を行ごとに Markdown へ変換')
st.markdown('---')

# CSV ファイルアップロード
uploaded_file = st.file_uploader('CSV ファイルをアップロードしてください', type=['csv'])

if uploaded_file is not None:
    try:
        # CSV をテキストとして読み込み
        uploaded_file.seek(0)
        csv_text = io.StringIO(uploaded_file.read().decode('utf-8'))
        reader = csv.reader(csv_text)
        rows = list(reader)
    except Exception as e:
        st.error(f'CSV の読み込みエラー: {e}')
        rows = []

    if rows:
        # 1行目をヘッダー、2行目以降をデータとする
        header = rows[0]
        data_rows = rows[1:]
        
        try:
            df = pd.DataFrame(data_rows, columns=header)
        except Exception as e:
            st.error(f'CSV プレビュー生成エラー: {e}')
            df = pd.DataFrame()
        
        st.markdown("## ファイル名")
        st.markdown("### ファイル名のカラムマッピング")
        # ファイル名に使用するカラムの選択
        title_column = st.selectbox(
            'Markdownファイル名に使用するカラムを選択してください。',
            header
        )

        # 正規表現による置換の設定
        st.markdown("### ファイル名のタイトルを置換する(optional)")
        st.markdown("ファイル名の特殊文字を変換したい場合に使用します。タイトルのプレビューは以下のCSVのプレビューから確認してください。置換しない場合は空欄にしてください。")
        regex_pattern = st.text_input('変換する正規表現パターン (例:URL文字列をファイル名として使う場合 `(:|/|\.)`)', value='')
        regex_replacement = st.text_input('正規表現にマッチした全ての文字列を箇所を以下の文字列で置換する', value='')

        st.markdown("### ファイル名が空値のレコードをエラー扱いにするか")
        empty_handling = st.radio(
            'ファイル名に選択したカラムの値が空のファイルが含まれる場合の処理を決定します。\nエラー: 空値が含まれていればマークダウンファイルの生成を失敗させます。\nスキップ: 空値になっているファイルの処理をスキップし、空値でないファイルのみをMarkdownに変換します。',
            options=['エラー', 'スキップ']
        )

        st.subheader('CSV のプレビュー (最大50行)')

        # --- 各行のファイル名候補の生成 ---
        file_name_list = []      # 各行の出力ファイル名（拡張子なし）
        file_name_counts = {}    # 同一名称への連番付与用
        empty_count = 0          # 空値の件数

        for row in data_rows:
            # 選択されたカラムの値を取得（前後の空白を除去）
            idx = header.index(title_column)
            original_value = row[idx].strip()
            
            # 正規表現が設定されている場合は置換を実施
            if regex_pattern:
                try:
                    converted_value = re.sub(regex_pattern, regex_replacement, original_value)
                except Exception as e:
                    st.error(f'正規表現エラー: {e}')
                    converted_value = original_value
            else:
                converted_value = original_value

            # 置換結果が空の場合は空文字として扱う
            if not converted_value:
                file_name_list.append("")
                empty_count += 1
            else:
                # 同じ名前が出た場合は通し番号を付与する
                base_name = converted_value
                if base_name in file_name_counts:
                    file_name_counts[base_name] += 1
                    converted_value = f"{base_name}_{file_name_counts[base_name]}"
                else:
                    file_name_counts[base_name] = 1
                file_name_list.append(converted_value)

        # プレビュー用に「生成ファイル名」カラムを追加（先頭50行のみ表示）
        df_preview = df.copy()
        df_preview['生成ファイル名'] = file_name_list[:len(df_preview)]
        st.dataframe(df_preview.head(50))
        
        if empty_count > 0:
            st.info(f'選択されたカラムにおいて、空の値が {empty_count} 件見つかりました。')

        # CSV を Markdown に変換するボタン
        if st.button('CSV を Markdown に変換'):
            if not data_rows:
                st.error('CSV の内容がありません。')
            else:
                # 「エラー」オプションの場合、空値があるなら変換を中断する
                if empty_handling == 'エラー' and empty_count > 0:
                    st.error(f'空の値が {empty_count} 件あります。変換を中止します。')
                else:
                    # メモリ上に ZIP ファイルを作成
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
                        for i, row in enumerate(data_rows):
                            file_name = file_name_list[i]
                            # 空の場合は「スキップ」オプションなら変換せずに次の行へ
                            if not file_name:
                                continue
                            # 各カラムを「# カラム名」とし、その下の行に値を記述
                            md_lines = []
                            for col, cell in zip(header, row):
                                md_lines.append(f"# {col}")
                                md_lines.append(cell)
                                md_lines.append("")  # 空行で区切り
                            md_content = "\n".join(md_lines)
                            # 拡張子 .md を付与して ZIP に書き込み
                            md_file_name = f"{file_name}.md"
                            zip_file.writestr(md_file_name, md_content)
                    
                    zip_buffer.seek(0)
                    
                    # スキップ件数がある場合はその件数も表示
                    if empty_handling == 'スキップ' and empty_count > 0:
                        st.info(f'{empty_count} 件の行は空の値のためスキップされました。')
                    
                    st.success('Markdown への変換が完了しました！')
                    
                    # ZIP ファイルダウンロード用ボタン
                    # 日本時間でのタイムスタンプを生成（9時間を加算）
                    current_time = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time() + 9 * 3600))
                    original_filename = uploaded_file.name.rsplit('.', 1)[0]  # 拡張子を除いたファイル名を取得
                    zip_filename = f"{original_filename}_{current_time}.zip"
                    
                    st.download_button(
                        label='ZIP ファイルをダウンロード',
                        data=zip_buffer.getvalue(),
                        file_name=zip_filename,
                        mime='application/zip'
                    )
    else:
        st.warning('CSV ファイルが空か、正しく読み込めませんでした。')
