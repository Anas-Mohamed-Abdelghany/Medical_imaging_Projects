using UnityEngine;
using TMPro;
using System.Collections;

public class PuzzleManager : MonoBehaviour 
{
    public TMP_Text timerText;
    public TMP_Text completionText;
    private PuzzlePiece[] puzzlePieces;
    private float startTime;
    private bool puzzleComplete = false;
    private int snappedPieces = 0;

    void Start()
    {
        puzzlePieces = FindObjectsByType<PuzzlePiece>(FindObjectsSortMode.None);

        for (int i = 0; i < puzzlePieces.Length; i++)
        {
            puzzlePieces[i].pieceIndex = i + 1;
        }

        if (completionText != null)
            completionText.gameObject.SetActive(false);

        startTime = Time.time;
        snappedPieces = 0;
    }

    void Update()
    {
        if (!puzzleComplete)
        {
            UpdateTimer();

            // Handle number key input for piece selection
            for (int i = 0; i < puzzlePieces.Length && i < 9; i++)
            {
                if (Input.GetKeyDown(KeyCode.Alpha1 + i))
                {
                    SelectPieceByIndex(i + 1);
                }
            }
        }
    }

    public void SelectPieceByIndex(int index)
    {
        foreach (var piece in puzzlePieces)
        {
            if (piece.pieceIndex == index && !piece.IsInCorrectPosition())
            {
                // Select this piece
                piece.isSelected = true;
                piece.GetComponent<Renderer>().material.color = Color.yellow;
            }
            else
            {
                // Deselect others
                piece.isSelected = false;
                if (!piece.IsInCorrectPosition())
                {
                    piece.GetComponent<Renderer>().material.color = Color.white;
                }
            }
        }
    }

    void UpdateTimer()
    {
        if (timerText != null)
        {
            float elapsedTime = Time.time - startTime;
            int minutes = (int)(elapsedTime / 60);
            int seconds = (int)(elapsedTime % 60);
            timerText.text = string.Format("Time: {0:00}:{1:00}", minutes, seconds);
        }
    }

    public void CheckPieceSnapped()
    {
        snappedPieces++;
        if (snappedPieces == puzzlePieces.Length)
        {
            StartCoroutine(ShowWinSequence());
        }
    }

    IEnumerator ShowWinSequence()
    {
        puzzleComplete = true;
        yield return new WaitForSeconds(1f);

        if (completionText != null)
        {
            float totalTime = Time.time - startTime;
            int minutes = (int)(totalTime / 60);
            int seconds = (int)(totalTime % 60);

            completionText.gameObject.SetActive(true);
            completionText.text = string.Format("CONGRATULATIONS!\nPuzzle Complete!\nTime: {0:00}:{1:00}", minutes, seconds);
        }
    }
}